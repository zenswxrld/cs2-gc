"""Read and write Source 2 compiled resources (*_c) and their binary KV3 blocks (versions 4 and 5).

Ported from the layout ValveResourceFormat reads and writes (BinaryKV3.cs / BinaryKV3.Serialization.cs).
Only the parts the native finish generator needs: version 4/5 KV3 with no compression or LZ4, written back
uncompressed. Python standard library only.

Values decode to Node(type, value, flag) so a round trip keeps every KV3 type; objects are lists of
(name, Node) pairs in file order.
"""
import struct

MAGIC4 = 0x4B563304
MAGIC5 = 0x4B563305
NULL, BOOLEAN, INT64, UINT64, DOUBLE, STRING, BINARY_BLOB, ARRAY, OBJECT, ARRAY_TYPED = range(1, 11)
INT32, UINT32, BOOLEAN_TRUE, BOOLEAN_FALSE, INT64_ZERO, INT64_ONE, DOUBLE_ZERO, DOUBLE_ONE, FLOAT = range(11, 20)
INT16, UINT16, INT8, UINT8, ARRAY_TYPE_BYTE_LENGTH, ARRAY_TYPE_AUXILIARY_BUFFER, UINT32_ZERO, UINT32_ONE = range(20, 28)
CONSTANTS = {NULL: None, BOOLEAN_TRUE: True, BOOLEAN_FALSE: False, INT64_ZERO: 0, INT64_ONE: 1,
             DOUBLE_ZERO: 0.0, DOUBLE_ONE: 1.0, UINT32_ZERO: 0, UINT32_ONE: 1}
LANES = {BOOLEAN: (1, '<B'), INT8: (1, '<b'), UINT8: (1, '<B'), INT16: (2, '<h'), UINT16: (2, '<H'),
         INT32: (4, '<i'), UINT32: (4, '<I'), FLOAT: (4, '<f'), INT64: (8, '<q'), UINT64: (8, '<Q'), DOUBLE: (8, '<d')}
TRAILER = 0xFFEEDD00


class Node:
    __slots__ = ('type', 'value', 'flag', 'subtype', 'subflag')

    def __init__(self, type, value, flag=0, subtype=None, subflag=0):
        self.type, self.value, self.flag, self.subtype, self.subflag = type, value, flag, subtype, subflag

    def __eq__(self, other):
        return isinstance(other, Node) and (self.type, self.value, self.flag, self.subtype, self.subflag) == \
            (other.type, other.value, other.flag, other.subtype, other.subflag)

    def __repr__(self):
        return 'Node(%r, %r)' % (self.type, self.value)

    def get(self, name):
        for key, value in self.value:
            if key == name: return value
        return None


def lz4_block_decompress(data, size):
    out = bytearray()
    i = 0
    while i < len(data):
        token = data[i]; i += 1
        literal = token >> 4
        if literal == 15:
            while True:
                extra = data[i]; i += 1; literal += extra
                if extra != 255: break
        out += data[i:i + literal]; i += literal
        if i >= len(data): break
        offset = data[i] | data[i + 1] << 8; i += 2
        if offset == 0: raise ValueError('Invalid LZ4 offset')
        match = token & 15
        if match == 15:
            while True:
                extra = data[i]; i += 1; match += extra
                if extra != 255: break
        match += 4
        start = len(out) - offset
        if start < 0: raise ValueError('Invalid LZ4 back-reference')
        for k in range(match): out.append(out[start + k])
    if len(out) != size: raise ValueError('LZ4 size mismatch: %d != %d' % (len(out), size))
    return bytes(out)


def _align(value, alignment):
    return (value + alignment - 1) // alignment * alignment


class _Lanes:
    def __init__(self, data, offset, counts):
        self.views = {}
        for width, count in zip((1, 2, 4, 8), counts):
            if count:
                offset = _align(offset, width)
                self.views[width] = [data, offset, offset + count * width]
                offset += count * width
        self.end = offset

    def take(self, width, fmt):
        view = self.views[width]
        value = struct.unpack_from(fmt, view[0], view[1])[0]
        view[1] += width
        if view[1] > view[2]: raise ValueError('KV3 lane overrun')
        return value

    def bytes1(self, length):
        view = self.views[1]
        value = bytes(view[0][view[1]:view[1] + length]); view[1] += length
        return value


def read_kv3(block):
    magic, = struct.unpack_from('<I', block, 0)
    if magic == MAGIC4: return read_kv4(block)
    if magic != MAGIC5: raise ValueError('Only binary KV3 version 5 is supported, got %#x' % magic)
    guid = block[4:20]
    (method, dictionary, frame, bytes1, bytes4, bytes8, count_types, objects, arrays, total, compressed_total,
     blocks, blob_bytes, bytes2, block_sizes, size1, csize1, size2, csize2, b1_2, b2_2, b4_2, b8_2,
     nodes, objects2, arrays2, elements) = struct.unpack_from('<IHHiiiiHHiiiiiiiiiiiiiiiiii', block, 20)
    if dictionary or blocks or blob_bytes: raise ValueError('KV3 dictionaries and binary blobs are not supported')
    position = 20 + struct.calcsize('<IHHiiiiHHiiiiiiiiiiiiiiiiii')
    if method == 0:
        buffer1 = block[position:position + size1]; position += size1
        buffer2 = block[position:position + size2]; position += size2
    elif method == 1:
        buffer1 = lz4_block_decompress(block[position:position + csize1], size1); position += csize1
        buffer2 = lz4_block_decompress(block[position:position + csize2], size2); position += csize2
    else:
        raise ValueError('Unsupported KV3 compression method %d' % method)
    auxiliary = _Lanes(buffer1, 0, (bytes1, bytes2, bytes4, bytes8))
    count_strings = auxiliary.take(4, '<i')
    strings = []
    for _ in range(count_strings):
        end = buffer1.index(b'\0', auxiliary.views[1][1])
        strings.append(buffer1[auxiliary.views[1][1]:end].decode('utf-8'))
        auxiliary.views[1][1] = end + 1
    object_lengths = [struct.unpack_from('<i', buffer2, 4 * i)[0] for i in range(objects2)]
    main = _Lanes(buffer2, objects2 * 4, (b1_2, b2_2, b4_2, b8_2))
    types = buffer2[main.end:main.end + count_types]
    state = {'types': 0, 'objects': 0}

    def read_type():
        byte = types[state['types']]; state['types'] += 1
        flag = 0
        if byte & 0x80:
            flag = types[state['types']]; state['types'] += 1
        if byte & 0x40:
            state['types'] += 1
        return byte & 0x3F, flag

    def string(index):
        return strings[index] if 0 <= index < len(strings) else ''

    def value(kind, flag, lane):
        if kind in CONSTANTS: return Node(kind, CONSTANTS[kind], flag)
        if kind in LANES: return Node(kind, lane.take(*LANES[kind]), flag)
        if kind == STRING: return Node(kind, string(main.take(4, '<i')), flag)
        if kind == ARRAY:
            length = main.take(4, '<i')
            return Node(kind, [value(*read_type(), main) for _ in range(length)], flag)
        if kind in (ARRAY_TYPED, ARRAY_TYPE_BYTE_LENGTH, ARRAY_TYPE_AUXILIARY_BUFFER):
            length = main.take(4, '<i') if kind == ARRAY_TYPED else main.take(1, '<B')
            subtype, subflag = read_type()
            source = auxiliary if kind == ARRAY_TYPE_AUXILIARY_BUFFER else main
            return Node(kind, [value(subtype, subflag, source) for _ in range(length)], flag, subtype, subflag)
        if kind == OBJECT:
            length = object_lengths[state['objects']]; state['objects'] += 1
            members = []
            for _ in range(length):
                subtype, subflag = read_type()
                name = string(main.take(4, '<i'))
                members.append((name, value(subtype, subflag, main)))
            return Node(kind, members, flag)
        raise ValueError('Unsupported KV3 node type %d' % kind)

    root = value(*read_type(), main)
    if struct.unpack_from('<I', buffer2, main.end + count_types)[0] != TRAILER: raise ValueError('Missing KV3 trailer')
    return guid, root



def read_kv4(block):
    """Read the single-buffer KV3 v4 layout; owned copies are written as KV3 v5.

    Layout reference: ValveResourceFormat BinaryKV3.ReadBuffer/ReadValue.
    No binary blobs, dictionaries or Zstd are accepted by this small codec.
    """
    header = '<IHHiiiiHHiiiiii'
    size = struct.calcsize(header)
    if len(block) < 20+size:
        raise ValueError('Truncated KV3 v4 header')
    (method,dictionary,frame,b1,b4,b8,type_bytes,objects,arrays,total,compressed,
     blocks,blob_bytes,b2,block_sizes) = struct.unpack_from(header,block,20)
    if dictionary or blocks or blob_bytes or block_sizes:
        raise ValueError('KV3 dictionaries and binary blobs are not supported')
    if min(b1,b2,b4,b8,type_bytes,total,compressed)<0:
        raise ValueError('Invalid KV3 v4 counts')
    payload=block[20+size:]
    if method==0:
        data=payload[:total]
        if len(data)!=total:
            raise ValueError('Truncated KV3 v4 buffer')
    elif method==1:
        data=lz4_block_decompress(payload[:compressed],total)
    else:
        raise ValueError('Unsupported KV3 compression method %d'%method)
    lane=_Lanes(data,0,(b1,b2,b4,b8))
    string_count=lane.take(4,'<i')
    position=lane.end if b8 else _align(lane.end,8)
    strings_start=position
    strings=[]
    for _ in range(string_count):
        end=data.index(b'\0',position)
        strings.append(data[position:end].decode('utf-8'));position=end+1
    length=type_bytes-(position-strings_start)
    if length<1 or position+length+4>len(data):
        raise ValueError('Invalid KV3 v4 type stream')
    types=data[position:position+length]
    if struct.unpack_from('<I',data,position+length)[0]!=TRAILER:
        raise ValueError('Missing KV3 trailer')
    cursor=0
    def read_type():
        nonlocal cursor
        byte=types[cursor];cursor+=1
        flag=0
        if byte&0x80:
            flag=types[cursor];cursor+=1
        if byte&0x40:
            cursor+=1
        return byte&0x3f,flag
    def string(index):
        return strings[index] if 0<=index<len(strings) else ''
    def value(kind,flag):
        if kind in CONSTANTS:
            return Node(kind,CONSTANTS[kind],flag)
        if kind in LANES:
            return Node(kind,lane.take(*LANES[kind]),flag)
        if kind==STRING:
            return Node(kind,string(lane.take(4,'<i')),flag)
        if kind==OBJECT:
            count=lane.take(4,'<i');members=[]
            for _ in range(count):
                subtype,subflag=read_type()
                name=string(lane.take(4,'<i'))
                members.append((name,value(subtype,subflag)))
            return Node(kind,members,flag)
        if kind==ARRAY:
            count=lane.take(4,'<i')
            return Node(kind,[value(*read_type()) for _ in range(count)],flag)
        if kind in (ARRAY_TYPED,ARRAY_TYPE_BYTE_LENGTH,ARRAY_TYPE_AUXILIARY_BUFFER):
            count=lane.take(4,'<i') if kind==ARRAY_TYPED else lane.take(1,'<B')
            subtype,subflag=read_type()
            return Node(kind,[value(subtype,subflag) for _ in range(count)],flag,subtype,subflag)
        raise ValueError('Unsupported KV3 node type %d'%kind)
    root=value(*read_type())
    if cursor!=len(types):
        raise ValueError('Unconsumed KV3 v4 types')
    return block[4:20],root


def write_kv3(guid, root):
    strings, lanes = {}, {1: bytearray(), 2: bytearray(), 4: bytearray(), 8: bytearray()}
    types, object_lengths = bytearray(), bytearray()
    counts = {'nodes': 0, 'arrays': 0, 'elements': 0}

    def string_id(text):
        if text not in strings: strings[text] = len(strings)
        return strings[text]

    def put(width, fmt, number):
        lanes[width] += struct.pack(fmt, number)

    def write_type(kind, flag):
        if flag:
            types.append(kind | 0x80); types.append(flag)
        else:
            types.append(kind)

    def write_value(node, typed=False):
        counts['nodes'] += 1
        kind = node.type
        if kind in CONSTANTS: return
        if kind in LANES: return put(*LANES[kind][::-1] if False else (LANES[kind][0], LANES[kind][1], node.value))
        if kind == STRING: return put(4, '<i', string_id(node.value))
        if kind == ARRAY:
            counts['arrays'] += 1; counts['elements'] += max(1, len(node.value))
            put(4, '<i', len(node.value))
            for item in node.value:
                write_type(item.type, item.flag); write_value(item)
            return
        if kind in (ARRAY_TYPED, ARRAY_TYPE_BYTE_LENGTH, ARRAY_TYPE_AUXILIARY_BUFFER):
            counts['arrays'] += 1; counts['elements'] += max(1, len(node.value))
            # Auxiliary-buffer arrays are written to the main lanes; readers accept either form.
            if len(node.value) < 256:
                put(1, '<B', len(node.value))
            else:
                put(4, '<i', len(node.value))
            write_type(node.subtype, node.subflag)
            for item in node.value: write_value(item)
            return
        if kind == OBJECT:
            object_lengths.extend(struct.pack('<i', len(node.value)))
            for name, item in node.value:
                write_type(item.type, item.flag)
                put(4, '<i', string_id(name))
                write_value(item)
            return
        raise ValueError('Unsupported KV3 node type %d' % kind)

    def retype(node):
        if node.type == ARRAY_TYPE_AUXILIARY_BUFFER or (node.type in (ARRAY_TYPED, ARRAY_TYPE_BYTE_LENGTH)):
            node = Node(ARRAY_TYPE_BYTE_LENGTH if len(node.value) < 256 else ARRAY_TYPED,
                        [retype(item) for item in node.value], node.flag, node.subtype, node.subflag)
        elif node.type == ARRAY:
            node = Node(ARRAY, [retype(item) for item in node.value], node.flag)
        elif node.type == OBJECT:
            node = Node(OBJECT, [(name, retype(item)) for name, item in node.value], node.flag)
        return node

    root = retype(root)
    write_type(root.type, root.flag)
    write_value(root)
    buffer1 = bytearray()
    for text in strings: buffer1 += text.encode('utf-8') + b'\0'
    string_bytes = len(buffer1)
    buffer1 += b'\0' * (_align(len(buffer1), 4) - len(buffer1))
    buffer1 += struct.pack('<i', len(strings))
    buffer2 = bytearray(object_lengths)
    for width in (1, 2, 4, 8):
        if lanes[width]:
            buffer2 += b'\0' * (_align(len(buffer2), width) - len(buffer2))
            buffer2 += lanes[width]
    buffer2 += types + struct.pack('<I', TRAILER)
    objects = len(object_lengths) // 4
    header = struct.pack('<I', MAGIC5) + guid + struct.pack(
        '<IHHiiiiHHiiiiiiiiiiiiiiiiii', 0, 0, 0, string_bytes, 1, 0, len(types), min(objects, 65535),
        min(counts['arrays'], 65535), len(buffer1) + len(buffer2), len(buffer1) + len(buffer2), 0, 0, 0, 0,
        len(buffer1), 0, len(buffer2), 0, len(lanes[1]), len(lanes[2]) // 2, len(lanes[4]) // 4, len(lanes[8]) // 8,
        counts['nodes'], objects, counts['arrays'], counts['elements'])
    return bytes(header + buffer1 + buffer2)


def read_resource(data):
    size, header_version, version, block_offset, block_count = struct.unpack_from('<IHHII', data, 0)
    if size != len(data) or header_version != 12: raise ValueError('Not a Source 2 compiled resource')
    blocks = []
    table = 8 + block_offset
    for index in range(block_count):
        entry = table + index * 12
        offset, length = struct.unpack_from('<II', data, entry + 4)
        start = entry + 4 + offset
        blocks.append([data[entry:entry + 4].decode('ascii'), data[start:start + length]])
    return version, blocks


def write_resource(version, blocks):
    table = 16
    position = _align(table + 12 * len(blocks), 16)
    entries, body = bytearray(), bytearray()
    for index, (name, content) in enumerate(blocks):
        entry = table + index * 12
        entries += name.encode('ascii') + struct.pack('<II', position - (entry + 4), len(content))
        body += content
        position += len(content)
        padding = _align(position, 16) - position
        if index + 1 < len(blocks): body += b'\0' * padding; position += padding
    head = bytearray(struct.pack('<IHHII', 0, 12, version, 8, len(blocks)) + entries)
    head += b'\0' * (_align(len(head), 16) - len(head))
    data = head + body
    struct.pack_into('<I', data, 0, len(data))
    return bytes(data)
