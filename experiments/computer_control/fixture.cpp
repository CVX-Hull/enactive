// Independent raw SDL fixture. It knows nothing about IPC or bridge internals.
#include <SDL2/SDL.h>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>

static std::string quoted(const char *value) {
    std::string out="\"";
    for(const unsigned char *p=(const unsigned char *)value;*p;++p) {
        if(*p=='"' || *p=='\\') { out+='\\'; out+=(char)*p; }
        else if(*p<32) { char escape[7]; snprintf(escape,sizeof escape,"\\u%04x",*p); out+=escape; }
        else out+=(char)*p;
    }
    return out+'"';
}
int main(int argc,char **argv) {
    if(argc<2) { fprintf(stderr,"usage: fixture EVENT_LOG.jsonl [--hidden] [--offscreen]\n"); return 2; }
    bool hidden=false,offscreen=false;
    for(int i=2;i<argc;++i) { if(strcmp(argv[i],"--hidden")==0) hidden=true; else if(strcmp(argv[i],"--offscreen")==0) offscreen=true; else return 2; }
    FILE *log=fopen(argv[1],"wx"); if(!log) { perror("event log"); return 2; }
    if(SDL_Init(SDL_INIT_VIDEO|SDL_INIT_EVENTS)!=0) { fprintf(stderr,"SDL_Init: %s\n",SDL_GetError()); fclose(log); return 1; }
    SDL_Window *window=SDL_CreateWindow("Mechanical SDL fixture",SDL_WINDOWPOS_CENTERED,SDL_WINDOWPOS_CENTERED,640,400,SDL_WINDOW_RESIZABLE|SDL_WINDOW_ALLOW_HIGHDPI|(hidden?SDL_WINDOW_HIDDEN:0));
    SDL_Renderer *renderer=window?SDL_CreateRenderer(window,-1,SDL_RENDERER_SOFTWARE):nullptr;
    if(!renderer) { fprintf(stderr,"SDL fixture: %s\n",SDL_GetError()); if(window) SDL_DestroyWindow(window); SDL_Quit(); fclose(log); return 1; }
    SDL_Texture *target=offscreen?SDL_CreateTexture(renderer,SDL_PIXELFORMAT_RGBA8888,SDL_TEXTUREACCESS_TARGET,123,77):nullptr;
    if(offscreen && !target) { fprintf(stderr,"SDL texture: %s\n",SDL_GetError()); return 1; }
    SDL_StartTextInput(); bool running=true; unsigned count=0,drain=0; int markerX=100,markerY=100; Uint8 red=40,green=100,blue=180; std::string text;
    while(running) {
        ++drain; SDL_Event e;
        while(SDL_PollEvent(&e)) {
            ++count; int mx=0,my=0,gx=0,gy=0; Uint32 buttons=SDL_GetMouseState(&mx,&my), globalButtons=SDL_GetGlobalMouseState(&gx,&gy); SDL_Keymod mods=SDL_GetModState();
            fprintf(log,"{\"event\":%u,\"drain\":%u,\"type\":%u,\"mouse\":[%d,%d],\"buttons\":%u,\"global_mouse\":[%d,%d],\"global_buttons\":%u,\"modifiers\":%u,\"offscreen\":%s",count,drain,e.type,mx,my,buttons,gx,gy,globalButtons,(unsigned)mods,SDL_GetRenderTarget(renderer)?"true":"false");
            if(e.type==SDL_KEYDOWN || e.type==SDL_KEYUP) {
                fprintf(log,",\"key\":%d,\"key_modifiers\":%u,\"repeat\":%u",e.key.keysym.sym,e.key.keysym.mod,e.key.repeat);
                if(e.type==SDL_KEYDOWN) { red=(Uint8)(red+37); if(e.key.keysym.sym==SDLK_ESCAPE) running=false; if(e.key.keysym.sym==SDLK_LEFT) markerX-=10; if(e.key.keysym.sym==SDLK_RIGHT) markerX+=10; if(e.key.keysym.sym==SDLK_UP) markerY-=10; if(e.key.keysym.sym==SDLK_DOWN) markerY+=10;
                    // Independent application behavior for mechanical tests only.
                    if(e.key.keysym.sym==SDLK_r) SDL_SetWindowSize(window,800,500);
                    if(e.key.keysym.sym==SDLK_d) {
                        if(target) { SDL_DestroyTexture(target); target=nullptr; }
                        SDL_DestroyRenderer(renderer); renderer=SDL_CreateRenderer(window,-1,SDL_RENDERER_SOFTWARE);
                        if(!renderer) { fprintf(stderr,"SDL replacement renderer: %s\n",SDL_GetError()); return 1; }
                        if(offscreen) target=SDL_CreateTexture(renderer,SDL_PIXELFORMAT_RGBA8888,SDL_TEXTUREACCESS_TARGET,123,77);
                    }
                    if(e.key.keysym.sym==SDLK_t) {
                        SDL_Event human={}; human.type=SDL_KEYDOWN; human.key.windowID=SDL_GetWindowID(window);
                        human.key.keysym.sym=SDLK_F1; SDL_PushEvent(&human);
                        human.type=SDL_KEYUP; SDL_PushEvent(&human);
                    }
                }
            } else if(e.type==SDL_TEXTINPUT) {
                text+=e.text.text; green=(Uint8)(green+29); fprintf(log,",\"text\":%s",quoted(e.text.text).c_str());
            } else if(e.type==SDL_MOUSEBUTTONDOWN || e.type==SDL_MOUSEBUTTONUP) {
                fprintf(log,",\"button\":%u,\"position\":[%d,%d]",e.button.button,e.button.x,e.button.y);
                if(e.type==SDL_MOUSEBUTTONDOWN) { markerX=e.button.x; markerY=e.button.y; blue=(Uint8)(blue+41); }
            } else if(e.type==SDL_MOUSEMOTION) fprintf(log,",\"position\":[%d,%d],\"motion_state\":%u",e.motion.x,e.motion.y,e.motion.state);
            else if(e.type==SDL_WINDOWEVENT) fprintf(log,",\"window_event\":%u,\"data\":[%d,%d]",e.window.event,e.window.data1,e.window.data2);
            fprintf(log,"}\n"); fflush(log);
            if(e.type==SDL_QUIT || (e.type==SDL_WINDOWEVENT && e.window.event==SDL_WINDOWEVENT_CLOSE)) running=false;
        }
        // Window title provides human-readable text feedback without a font dependency.
        std::string title="Mechanical SDL fixture | events="+std::to_string(count)+" | text="+text;
        SDL_SetWindowTitle(window,title.c_str());
        SDL_SetRenderTarget(renderer,nullptr);
        SDL_SetRenderDrawColor(renderer,red,green,blue,255); SDL_RenderClear(renderer);
        SDL_SetRenderDrawColor(renderer,255,255,255,255); SDL_Rect marker={markerX-8,markerY-8,16,16}; SDL_RenderFillRect(renderer,&marker);
        // Text bytes have a visible, deterministic stripe representation in pixels.
        int x=12; for(unsigned char c:text) { SDL_SetRenderDrawColor(renderer,c,(Uint8)(255-c),220,255); SDL_Rect bar={x,12,5,8+(c%40)}; SDL_RenderFillRect(renderer,&bar); x+=7; if(x>600) break; }
        SDL_RenderPresent(renderer); if(target) SDL_SetRenderTarget(renderer,target); SDL_Delay(16);
    }
    SDL_StopTextInput(); if(target) SDL_DestroyTexture(target); SDL_DestroyRenderer(renderer); SDL_DestroyWindow(window); SDL_Quit(); fclose(log); return 0;
}
