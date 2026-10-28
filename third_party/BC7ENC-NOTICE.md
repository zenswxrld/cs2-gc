# bc7enc

Unmodified `bc7enc.cpp` and `bc7enc.h` by Richard Geldreich, Jr., from https://github.com/richgel999/bc7enc_rdo
(commit b9438627eef73a1157e84201b6fa6eb2ffd6d9f0). Used under the MIT license option stated in that repository's LICENSE:

> Copyright(c) 2020-2021 Richard Geldreich, Jr.
>
> Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
> documentation files (the "Software"), to deal in the Software without restriction, including without limitation the
> rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit
> persons to whom the Software is furnished to do so, subject to the following conditions:
>
> The above copyright notice and this permission notice shall be included in all copies or substantial portions of the
> Software.
>
> THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE
> WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
> COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
> OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

It encodes the recoloured collection textures back to BC7, the format CS2's own finishes use (user, 28 Oct: smaller
and faster than storing full BGRA pixels). All recolour logic is in our own texture_decode.cpp.
