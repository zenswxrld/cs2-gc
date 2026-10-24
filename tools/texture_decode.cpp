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
int main(int argc,char**argv) {
#ifdef _WIN32
    _setmode(_fileno(stdin),_O_BINARY);_setmode(_fileno(stdout),_O_BINARY);
#endif
    if(argc!=3 && argc!=6) return 2;
    int w=std::atoi(argv[1]),h=std::atoi(argv[2]);
    if(w<1||h<1||w>4096||h>4096) return 3;
    std::vector<unsigned char> input((std::istreambuf_iterator<char>(std::cin)),{});
    std::size_t blocksX=(w+3)/4,blocksY=(h+3)/4;
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
    std::size_t changed=0,eligible=0;
    std::array<std::size_t,4096> histogram{};
    std::array<std::array<unsigned char,4>,4096> samples{};
    if(argc==6) {
        float target=std::strtof(argv[3],nullptr)/360,cap=std::strtof(argv[4],nullptr);
        int mode=std::atoi(argv[5]);
        if(mode<0||mode>3) return 5;
        bool ramp=mode==1;
        float anchor=0;
        if(mode==2) {
            std::array<std::size_t,360> hues{};
            for(std::size_t p=0;p<pixels.size();p+=4) {
                auto c=hsv(pixels[p]/255.f,pixels[p+1]/255.f,pixels[p+2]/255.f);
                if(c[1]>=.18f&&c[2]>=.15f&&pixels[p+3]!=0)
                    ++hues[std::min(359,int(c[0]*360))];
            }
            anchor=float(std::max_element(hues.begin(),hues.end())-hues.begin())/360;
            float delta=std::abs(target-anchor);delta-=std::floor(delta);
            if(std::min(delta,1-delta)<25.f/360) return 7;
        }
        if(!std::isfinite(target)||!std::isfinite(cap)||cap<0||cap>1) return 5;
        for(std::size_t p=0;p<pixels.size();p+=4) {
            auto c=hsv(pixels[p]/255.f,pixels[p+1]/255.f,pixels[p+2]/255.f);
            // Grayscale foil, dark ink and transparent artwork are protected.
            if(pixels[p+3]==0) continue;
            if(mode==3) {
                if(c[1]>.12f) continue; // Neutral Printstream body/ink only.
            } else if(c[1]<.18f||c[2]<.15f) continue;
            float distance=std::min(c[0],1-c[0]);
            if(mode==0 && distance>40.f/360) continue; // Foil: only the authored red lacquer.
            ++eligible;
            float hue=ramp?target+std::sin(c[0]*6.28318530718f)*38.f/360:
                target+(c[0]>.5f?c[0]-1:c[0]);
            if(mode==2) hue=c[0]+target-anchor;
            auto v=rgb(hue,std::min(c[1],cap),c[2]);
            if(mode==3) v={1-pixels[p]/255.f,1-pixels[p+1]/255.f,1-pixels[p+2]/255.f};
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
