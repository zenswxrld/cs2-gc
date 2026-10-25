// BC7 decoding uses the unmodified MIT-licensed bcdec header (see third_party/bcdec.h).
#define BCDEC_IMPLEMENTATION
#include "../third_party/bcdec.h"
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <iterator>
#include <vector>
#include <string>
#include <cstring>
#ifndef CS2_GC_TEXTURE_PIPELINE_HASH
#define CS2_GC_TEXTURE_PIPELINE_HASH "development"
#endif
#ifdef _WIN32
#include <fcntl.h>
#include <io.h>
#endif
static std::array<float,3> hsv(float r,float g,float b) {
    float v=std::max({r,g,b}),lo=std::min({r,g,b}),d=v-lo,h=0;
    if(d>0) {
        if(v==r) h=(g-b)/d;
        else if(v==g) h=2+(b-r)/d;
        else h=4+(r-g)/d;
        h/=6; h-=std::floor(h);
    }
    return {h,v>0?d/v:0,v};
}
static std::array<float,3> rgb(float h,float s,float v) {
    h-=std::floor(h); float t=h*6; int i=int(t); float f=t-i;
    float p=v*(1-s),q=v*(1-s*f),u=v*(1-s*(1-f));
    switch(i%6) {
        case 0:return {v,u,p};case 1:return {q,v,p};case 2:return {p,v,u};
        case 3:return {p,q,v};case 4:return {u,p,v};default:return {v,p,q};
    }
}
static bool protectedArtwork(const std::array<float,3>& c,int mode) {
    // Keep natural warm portrait tones and the gold framing on blue-ink porcelain.
    if(mode==6 && c[0]>=18.f/360 && c[0]<=50.f/360 &&
        c[1]>=.18f && c[1]<=.65f && c[2]>=.35f) return true;
    return mode==7 && (c[0]<160.f/360 || c[0]>265.f/360);
}
// Lossless block compression for full-resolution owned artwork textures.
static std::vector<unsigned char> lz4(const std::vector<unsigned char>& in) {
    std::vector<unsigned char> out;
    std::array<int,65536> table;table.fill(-1);
    auto length=[&](std::size_t n) {while(n>=255){out.push_back(255);n-=255;}out.push_back(static_cast<unsigned char>(n));};
    auto hash=[&](std::size_t p) {std::uint32_t v=std::uint32_t(in[p])|(std::uint32_t(in[p+1])<<8)|(std::uint32_t(in[p+2])<<16)|(std::uint32_t(in[p+3])<<24);return (v*2654435761u)>>16;};
    std::size_t anchor=0,p=0;
    while(p+12<=in.size()) {
        auto h=hash(p);int previous=table[h];table[h]=static_cast<int>(p);
        if(previous<0 || p-std::size_t(previous)>65535 || !std::equal(in.begin()+previous,in.begin()+previous+4,in.begin()+p)) {++p;continue;}
        std::size_t match=4,ref=std::size_t(previous);
        while(p+match<in.size()-5 && in[ref+match]==in[p+match])++match;
        auto literals=p-anchor,extra=match-4;
        out.push_back(static_cast<unsigned char>((std::min<std::size_t>(15,literals)<<4)|std::min<std::size_t>(15,extra)));
        if(literals>=15)length(literals-15);
        out.insert(out.end(),in.begin()+anchor,in.begin()+p);
        auto offset=p-ref;out.push_back(static_cast<unsigned char>(offset));out.push_back(static_cast<unsigned char>(offset>>8));
        if(extra>=15)length(extra-15);
        p+=match;anchor=p;
    }
    auto literals=in.size()-anchor;
    out.push_back(static_cast<unsigned char>(std::min<std::size_t>(15,literals)<<4));
    if(literals>=15)length(literals-15);
    out.insert(out.end(),in.begin()+anchor,in.end());
    return out;
}

static bool readInput(std::vector<unsigned char>& data,std::size_t limit) {
    std::array<char,65536> block;
    while(std::cin) {
        std::cin.read(block.data(),block.size());auto count=std::size_t(std::cin.gcount());
        if(count>limit-data.size())return false;
        data.insert(data.end(),block.data(),block.data()+count);
    }
    return std::cin.eof();
}

static bool unlz4(const std::vector<unsigned char>& in,std::size_t size,std::vector<unsigned char>& out) {
    out.clear();out.reserve(size);std::size_t p=0;
    auto length=[&](std::size_t& n) {
        if(n!=15)return true;
        unsigned extra;
        do {if(p==in.size())return false;extra=in[p++];if(extra>size-n)return false;n+=extra;} while(extra==255);
        return true;
    };
    while(p<in.size()) {
        auto token=in[p++];std::size_t literals=token>>4;
        if(literals>size||!length(literals)||literals>in.size()-p||literals>size-out.size())return false;
        out.insert(out.end(),in.begin()+p,in.begin()+p+literals);p+=literals;
        if(p==in.size())return out.size()==size;
        if(in.size()-p<2)return false;
        std::size_t offset=in[p]|(std::size_t(in[p+1])<<8);p+=2;
        if(!offset||offset>out.size())return false;
        std::size_t match=token&15;
        if(match>size||!length(match)||size-out.size()<4||match>size-out.size()-4)return false;
        match+=4;auto start=out.size();out.resize(start+match);
        auto copied=std::min(match,offset);
        std::memcpy(out.data()+start,out.data()+start-offset,copied);
        while(copied<match) {
            auto count=std::min(copied,match-copied);
            std::memcpy(out.data()+start+copied,out.data()+start,count);copied+=count;
        }
    }
    return out.size()==size;
}


int main(int argc,char**argv) {
#ifdef _WIN32
    _setmode(_fileno(stdin),_O_BINARY);_setmode(_fileno(stdout),_O_BINARY);
#endif
    if(argc==2 && std::string(argv[1])=="--cache-version") {
        std::cout<<"cs2gc-artwork-v2:"<<CS2_GC_TEXTURE_PIPELINE_HASH<<"\n";return 0;
    }
    if(argc==3 && std::string(argv[1])=="--unlz4") {
        char* end=nullptr;auto size=std::strtoull(argv[2],&end,10);
        if(!end||*end||size>(1u<<27))return 3;
        std::vector<unsigned char> input,decoded;
        if(!readInput(input,1u<<27)||!unlz4(input,std::size_t(size),decoded))return 4;
        std::cout.write(reinterpret_cast<const char*>(decoded.data()),static_cast<std::streamsize>(decoded.size()));
        return std::cout?0:6;
    }
    if(argc==2 && std::string(argv[1])=="--lz4") {
        std::vector<unsigned char> input,verified;
        if(!readInput(input,1u<<27))return 3;
        auto compressed=lz4(input);
        if(!unlz4(compressed,input.size(),verified)||verified!=input)return 6;
        std::cout.write(reinterpret_cast<const char*>(compressed.data()),static_cast<std::streamsize>(compressed.size()));
        return std::cout?0:6;
    }
    bool auditOnly=argc==4 && std::string(argv[3])=="--audit";
    if(argc!=3 && argc!=6 && argc!=7 && !auditOnly) return 2;
    int w=std::atoi(argv[1]),h=std::atoi(argv[2]);
    if(w<1||h<1||w>4096||h>4096) return 3;
    std::size_t blocksX=(w+3)/4,blocksY=(h+3)/4;
    std::vector<unsigned char> input;input.reserve(blocksX*blocksY*16);
    if(!readInput(input,blocksX*blocksY*16))return 4;
    if(input.size()!=blocksX*blocksY*16) return 4;
    std::vector<unsigned char> pixels(std::size_t(w)*h*4);
    std::array<unsigned char,64> block{};
    for(std::size_t y=0;y<blocksY;++y) for(std::size_t x=0;x<blocksX;++x) {
        bcdec_bc7(input.data()+(y*blocksX+x)*16,block.data(),16);
        for(int j=0;j<4;++j) for(int i=0;i<4;++i) {
            int xx=int(x)*4+i,yy=int(y)*4+j;
            if(xx<w&&yy<h) std::copy_n(block.data()+(j*4+i)*4,4,pixels.data()+(yy*w+xx)*4);
        }
    }
    if(auditOnly) {
        std::size_t chromatic=0,masked=0,neutral=0,maskedNeutral=0;
        for(std::size_t p=0;p<pixels.size();p+=4) {
            auto c=hsv(pixels[p]/255.f,pixels[p+1]/255.f,pixels[p+2]/255.f);
            if(c[1]>=.18f&&c[2]>=.15f) {++chromatic;if(pixels[p+3]==0)++masked;}
            if(c[1]<=.12f) {++neutral;if(pixels[p+3]==0)++maskedNeutral;}
        }
        std::cout<<"{\"chromatic_pixels\":"<<chromatic<<",\"zero_alpha_chromatic_pixels\":"<<masked
                 <<",\"neutral_pixels\":"<<neutral<<",\"zero_alpha_neutral_pixels\":"<<maskedNeutral<<"}\n";
        return std::cout?0:6;
    }
    std::size_t changed=0,eligible=0;
    std::array<std::size_t,4096> histogram{};
    std::array<std::array<unsigned char,4>,4096> samples{};
    if(argc==6 || argc==7) {
        float target=std::strtof(argv[3],nullptr)/360,cap=std::strtof(argv[4],nullptr);
        int mode=std::atoi(argv[5]);
        if(mode<0||mode>10 || (mode==10)!=(argc==7)) return 5;
        float accent=mode==10?std::strtof(argv[6],nullptr)/360:0;
        if(!std::isfinite(accent))return 5;
        // Paint alpha carries finish masks, not opacity. These opt-in modes
        // recolour RGB on zero-alpha paint islands while preserving the mask.
        bool materialAlpha=mode==4||mode==5||mode==8||mode==9||mode==10;
        bool coordinated=mode==5||mode==9;
        bool inverse=mode==3||mode==8;
        bool rotate=mode==2||mode==6||mode==7||mode==4||mode==10||coordinated;
        bool ramp=mode==1;
        float anchor=0;
        if(rotate) {
            std::array<std::size_t,360> hues{};
            for(std::size_t p=0;p<pixels.size();p+=4) {
                auto c=hsv(pixels[p]/255.f,pixels[p+1]/255.f,pixels[p+2]/255.f);
                if(c[1]>=.18f&&c[2]>=.15f&&(materialAlpha||pixels[p+3]!=0)&&!protectedArtwork(c,mode==9?6:mode))
                    ++hues[std::min(359,int(c[0]*360))];
            }
            anchor=float(std::max_element(hues.begin(),hues.end())-hues.begin())/360;
            float delta=std::abs(target-anchor);delta-=std::floor(delta);
            if(!coordinated && mode!=10 && std::min(delta,1-delta)<25.f/360) return 7;
        }
        if(!std::isfinite(target)||!std::isfinite(cap)||cap<0||cap>1) return 5;
        for(std::size_t p=0;p<pixels.size();p+=4) {
            auto c=hsv(pixels[p]/255.f,pixels[p+1]/255.f,pixels[p+2]/255.f);
            // Grayscale foil, dark ink and transparent artwork are protected.
            if(!materialAlpha && pixels[p+3]==0) continue;
            if(inverse) {
                if(c[1]>.12f) continue; // Neutral Printstream body/ink only.
            } else if(c[1]<.18f||c[2]<.15f) continue;
            float distance=std::min(c[0],1-c[0]);
            if(mode==0 && distance>40.f/360) continue; // Foil: only the authored red lacquer.
            if(protectedArtwork(c,mode==9?6:mode)) continue;
            ++eligible;
            float hue=ramp?target+std::sin(c[0]*6.28318530718f)*38.f/360:
                target+(c[0]>.5f?c[0]-1:c[0]);
            if(rotate) hue=c[0]+target-anchor;
            if(coordinated) {
                float delta=c[0]-anchor;delta-=std::floor(delta+.5f);
                hue=target+std::clamp(delta,-.5f,.5f)*.10f;
            }
            if(mode==10) {
                // Separate the dominant authored ink from its accent family.
                // Keep local hue variation, saturation, value and exact alpha;
                // never compress both colours onto one hue as mode 5 does.
                float delta=c[0]-anchor;delta-=std::floor(delta+.5f);
                float distance=std::abs(delta)*360;
                float blend=std::clamp((distance-38.f)/32.f,0.f,1.f);
                blend=blend*blend*(3-2*blend);
                float arc=accent-target;arc-=std::floor(arc+.5f);
                hue=target+arc*blend+std::clamp(delta,-.08f,.08f)*.35f;
            }
            auto v=rgb(hue,std::min(c[1],cap),c[2]);
            if(inverse) v={1-pixels[p]/255.f,1-pixels[p+1]/255.f,1-pixels[p+2]/255.f};
            bool differs=false;
            for(int channel=0;channel<3;++channel) {
                auto value=static_cast<unsigned char>(std::clamp(int(std::lround(v[channel]*255)),0,255));
                differs=differs||value!=pixels[p+channel];pixels[p+channel]=value;
            }
            if(differs) {
                ++changed;
                unsigned bin=(pixels[p]>>4)*256+(pixels[p+1]>>4)*16+(pixels[p+2]>>4);
                ++histogram[bin];std::copy_n(pixels.data()+p,4,samples[bin].data());
            }
        }
    }
    std::cerr<<"{\"changed_pixels\":"<<changed<<",\"eligible_pixels\":"<<eligible<<",\"palette\":[";
    bool comma=false;
    for(int rank=0;rank<4;++rank) {
        auto best=std::max_element(histogram.begin(),histogram.end());
        if(*best==0) break;
        auto index=static_cast<std::size_t>(best-histogram.begin());
        if(comma) std::cerr<<",";
        comma=true;std::cerr<<"[";
        for(int channel=0;channel<4;++channel) {
            if(channel) std::cerr<<",";
            std::cerr<<static_cast<unsigned>(samples[index][channel])/255.f;
        }
        std::cerr<<"]";*best=0;
    }
    std::cerr<<"]}\n";
    std::cout.write(reinterpret_cast<const char*>(pixels.data()),static_cast<std::streamsize>(pixels.size()));
    return std::cout?0:6;
}
