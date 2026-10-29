// Experimental mechanical SDL boundary. No engine or widget dependencies.
#import <Foundation/Foundation.h>
#include <SDL2/SDL.h>
#include <SDL2_image/SDL_image.h>
#include <sys/file.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <algorithm>
#include <cerrno>
#include <cmath>
#include <cstring>
#include <cstdint>
#include <mutex>
#include <stdexcept>
#include <string>
#include <vector>
// The SDK may omit dyld-interposing.h. This is the two-pointer dyld ABI,
// declared locally rather than vendoring the upstream header.
// https://github.com/apple-oss-distributions/dyld/blob/main/include/mach-o/dyld-interposing.h
struct InterposeEntry { const void *substitute; const void *original; };

namespace {
constexpr size_t MaxFrame = 64 * 1024 * 1024;
constexpr long long MaxInteger = 9007199254740991LL;
struct Fault : std::runtime_error { using std::runtime_error::runtime_error; };
long long nowMS() { return (long long)([[NSDate date] timeIntervalSince1970] * 1000.0); }
void require(bool ok, const char *why) { if (!ok) throw Fault(why); }
bool string(id value) { return [value isKindOfClass:[NSString class]]; }
bool number(id value, long long low, long long high) {
    if (![value isKindOfClass:[NSNumber class]] || CFGetTypeID((__bridge CFTypeRef)value) == CFBooleanGetTypeID()) return false;
    double n = [value doubleValue];
    return std::isfinite(n) && floor(n) == n && n >= low && n <= high;
}
bool closed(id value, NSArray *keys) {
    return [value isKindOfClass:[NSDictionary class]] && [value count] == [keys count] &&
        [[NSSet setWithArray:[value allKeys]] isEqual:[NSSet setWithArray:keys]];
}
bool exists(NSString *path) { struct stat st; return lstat(path.fileSystemRepresentation, &st) == 0; }
NSString *join(NSString *a, NSString *b) { return [a stringByAppendingPathComponent:b]; }

NSData *regularData(NSString *path) {
    int fd=open(path.fileSystemRepresentation, O_RDONLY|O_NOFOLLOW|O_CLOEXEC);
    require(fd>=0, "Cannot open request");
    struct stat st; bool valid=fstat(fd,&st)==0 && S_ISREG(st.st_mode) && st.st_size>0 && st.st_size<=65536;
    if (!valid) { close(fd); throw Fault("Invalid bounded regular request"); }
    NSMutableData *data=[NSMutableData dataWithLength:(NSUInteger)st.st_size];
    size_t done=0; while (done<data.length) { ssize_t n=read(fd,(char *)data.mutableBytes+done,data.length-done); if(n<=0) { close(fd); throw Fault("Cannot read request"); } done+=(size_t)n; }
    close(fd); return data;
}
void writeJSON(NSString *path, id value, bool immutable=false) {
    NSError *error=nil; NSData *data=[NSJSONSerialization dataWithJSONObject:value options:0 error:&error];
    require(data!=nil, "Cannot encode JSON");
    NSString *temp=[path stringByAppendingFormat:@".native-%d.tmp",getpid()];
    int fd=open(temp.fileSystemRepresentation,O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW|O_CLOEXEC,0600);
    require(fd>=0, "Cannot create JSON temporary");
    size_t done=0;
    while(done<data.length) { ssize_t n=write(fd,(const char *)data.bytes+done,data.length-done); if(n<0 && errno==EINTR) continue; if(n<=0) { close(fd); unlink(temp.fileSystemRepresentation); throw Fault("Cannot write JSON"); } done+=(size_t)n; }
    bool ok=close(fd)==0;
    if(ok) ok=immutable ? link(temp.fileSystemRepresentation,path.fileSystemRepresentation)==0 : rename(temp.fileSystemRepresentation,path.fileSystemRepresentation)==0;
    int saved=errno; unlink(temp.fileSystemRepresentation);
    require(ok || (immutable && saved==EEXIST), "Cannot publish JSON");
}
bool identity(id value) {
    if(!string(value) || [value length]!=32) return false;
    return [value rangeOfCharacterFromSet:[[NSCharacterSet characterSetWithCharactersInString:@"0123456789abcdef"] invertedSet]].location==NSNotFound;
}
bool geometry(id g) {
    if(!closed(g,@[@"width",@"height",@"window_width",@"window_height",@"viewport"])) return false;
    for(NSString *key in @[@"width",@"height",@"window_width",@"window_height"]) if(!number(g[key],1,16384)) return false;
    id v=g[@"viewport"]; if(![v isKindOfClass:[NSArray class]] || [v count]!=4) return false;
    for(id n in v) if(!number(n,0,16384)) return false;
    return [v[2] intValue]>0 && [v[3] intValue]>0 && [v[0] intValue]+[v[2] intValue]<=[g[@"width"] intValue] && [v[1] intValue]+[v[3] intValue]<=[g[@"height"] intValue];
}
SDL_Keycode keycode(NSString *key) {
    NSDictionary *names=@{@"ENTER":@(SDLK_RETURN),@"ESC":@(SDLK_ESCAPE),@"UP":@(SDLK_UP),@"DOWN":@(SDLK_DOWN),@"LEFT":@(SDLK_LEFT),@"RIGHT":@(SDLK_RIGHT),@"TAB":@(SDLK_TAB),@"BACKSPACE":@(SDLK_BACKSPACE),@"SPACE":@(SDLK_SPACE),@"PAGEUP":@(SDLK_PAGEUP),@"PAGEDOWN":@(SDLK_PAGEDOWN),@"HOME":@(SDLK_HOME),@"END":@(SDLK_END),@"DELETE":@(SDLK_DELETE)};
    if(names[key]) return [names[key] intValue];
    require(string(key) && key.length==1 && [key characterAtIndex:0]>=32 && [key characterAtIndex:0]<=126,"Unsupported basic key");
    return (SDL_Keycode)[key characterAtIndex:0];
}
struct Bridge {
    std::recursive_mutex mutex;
    bool initialized=false, enabled=false, paused=false, lost=false, yieldEmpty=false, pointer=false, human=false;
    int lockFD=-1; NSString *dir=nil, *session=nil, *error=@"";
    SDL_Renderer *renderer=nullptr; SDL_Window *window=nullptr; Uint32 windowID=0;
    uint64_t generation=0, captureID=0; long long presented=0;
    NSDictionary *currentGeometry=nil, *latestFrame=nil, *request=nil;
    int windowPixelsW=0, windowPixelsH=0;
    std::vector<Uint8> pixels; std::vector<SDL_Event> stages; size_t next=0; unsigned emitted=0;
    std::vector<SDL_Keycode> held; Uint32 buttons=0; SDL_Keymod modifiers=KMOD_NONE; int mouseX=0,mouseY=0;
    NSString *failure=nil;
    void pause(NSString *why, bool takeover=false) {
        if(takeover && !human) { ++generation; human=true; }
        paused=true; error=why;
        if(takeover) { pointer=false; modifiers=KMOD_NONE; }
    }
    void init() {
        if(initialized) return; initialized=true;
        const char *path=getenv("ENACTIVE_COMPUTER_DIR"), *token=getenv("ENACTIVE_COMPUTER_SESSION");
        if(!path || !token || !*token || getenv("CDDA_HARNESS_DIR")) return;
        dir=[NSString stringWithUTF8String:path]; session=[NSString stringWithUTF8String:token];
        require(dir && session && session.length<=128,"Invalid native environment");
        struct stat st; require(lstat(path,&st)==0 && S_ISDIR(st.st_mode) && (st.st_mode&0777)==0700 && st.st_uid==getuid(),"IPC directory must be owned0700");
        lockFD=open(join(dir,@"native.lock").fileSystemRepresentation,O_RDWR|O_CREAT|O_NOFOLLOW|O_CLOEXEC,0600);
        require(lockFD>=0 && flock(lockFD,LOCK_EX|LOCK_NB)==0,"Native writer already exists");
        require(mkdir(join(dir,@"receipts").fileSystemRepresentation,0700)==0 || errno==EEXIST,"Cannot create receipt directory");
        require(!exists(join(dir,@"claimed.json")),"Existing claimed request forbids adoption");
        enabled=true; state();
    }
    void state() {
        if(!enabled) return;
        writeJSON(join(dir,@"state.json"),@{@"schema":@"computer-target/1",@"session":session,@"pid":@(getpid()),@"window_id":@(windowID),@"paused":@(paused),@"takeover_generation":@(generation),@"latest_frame":latestFrame?:[NSNull null],@"error":error});
    }
    void fence() {
        bool wasPaused=paused;
        if(exists(join(dir,@"pause"))) pause(@"External Pause");
        const char *token=getenv("ENACTIVE_COMPUTER_SESSION");
        if(!token || ![session isEqualToString:[NSString stringWithUTF8String:token]] || getenv("CDDA_HARNESS_DIR")) pause(@"Session environment changed");
        if(windowID && (lost || !window || !renderer || SDL_GetWindowFromID(windowID)!=window)) pause(@"Bound target lost");
        if(!wasPaused && paused) state();
    }
    NSDictionary *measure() {
        require(window && renderer && SDL_GetRenderTarget(renderer)==nullptr,"Default renderer target required");
        int w=0,h=0,ww=0,wh=0,lw=0,lh=0; float sx=0,sy=0;
        require(SDL_GetRendererOutputSize(renderer,&w,&h)==0,"Cannot measure renderer");
        SDL_GetWindowSize(window,&ww,&wh); SDL_RenderGetLogicalSize(renderer,&lw,&lh); SDL_RenderGetScale(renderer,&sx,&sy);
        require(lw==0 && lh==0 && sx==1.0f && sy==1.0f,"Logical-size or renderer-scale transform unsupported");
        SDL_Rect v; SDL_RenderGetViewport(renderer,&v);
        NSDictionary *g=@{@"width":@(w),@"height":@(h),@"window_width":@(ww),@"window_height":@(wh),@"viewport":@[@(v.x),@(v.y),@(v.w),@(v.h)]};
        require(geometry(g) && (size_t)w*(size_t)h*4<=MaxFrame,"Capture geometry outside bound"); return g;
    }
    void bind(SDL_Renderer *r) {
        init(); if(!enabled || renderer || lost) return;
        SDL_Window *w=SDL_RenderGetWindow(r); require(w!=nullptr,"Renderer has no window");
        renderer=r; window=w; windowID=SDL_GetWindowID(w); state();
    }
    void capture(SDL_Renderer *r) {
        bind(r); if(!enabled || r!=renderer || lost) return;
        NSDictionary *g=measure(); size_t size=(size_t)[g[@"width"] intValue]*[g[@"height"] intValue]*4;
        std::vector<Uint8> buffer(size);
        require(SDL_RenderReadPixels(r,nullptr,SDL_PIXELFORMAT_RGBA32,buffer.data(),[g[@"width"] intValue]*4)==0,"Renderer readback failed");
        SDL_GetWindowSizeInPixels(window,&windowPixelsW,&windowPixelsH);
        require(windowPixelsW>0 && windowPixelsH>0,"Window pixel geometry unavailable");
        pixels.swap(buffer); currentGeometry=g; ++captureID; presented=nowMS(); if(!paused) error=@"";
    }
    void pointerGeometry(id g) {
        require(currentGeometry && [g isEqual:currentGeometry],"Pointer geometry changed");
        int ww=0,wh=0,pw=0,ph=0; SDL_GetWindowSize(window,&ww,&wh); SDL_GetWindowSizeInPixels(window,&pw,&ph);
        require(ww==[g[@"window_width"] intValue] && wh==[g[@"window_height"] intValue] &&
                pw==windowPixelsW && ph==windowPixelsH,"Pointer window geometry changed");
        // SDL's active-target output/viewport/scale describe an offscreen texture,
        // not pointer mapping. Never switch the application's target to inspect it.
        if(SDL_GetRenderTarget(renderer)==nullptr) require([g isEqual:measure()],"Pointer geometry changed");
    }
    NSDictionary *saveFrame() {
        require(captureID>0 && !pixels.empty() && currentGeometry,"No presented capture");
        // Snapshot from the last actual present; never render or read hidden state.
        NSString *name=[NSString stringWithFormat:@"frame-%llu.png",(unsigned long long)captureID];
        NSString *path=join(dir,name);
        if(!exists(path)) {
            NSString *temp=[path stringByAppendingString:@".native.tmp"];
            SDL_Surface *surface=SDL_CreateRGBSurfaceWithFormatFrom(pixels.data(),[currentGeometry[@"width"] intValue],[currentGeometry[@"height"] intValue],32,[currentGeometry[@"width"] intValue]*4,SDL_PIXELFORMAT_RGBA32);
            require(surface!=nullptr,"Cannot wrap captured pixels"); int rc=IMG_SavePNG(surface,temp.fileSystemRepresentation); SDL_FreeSurface(surface);
            require(rc==0,"PNG encoding failed");
            struct stat st; if(stat(temp.fileSystemRepresentation,&st)!=0 || st.st_size<=0 || (size_t)st.st_size>MaxFrame) { unlink(temp.fileSystemRepresentation); throw Fault("PNG outside byte bound"); }
            int linked=link(temp.fileSystemRepresentation,path.fileSystemRepresentation); int saved=errno; unlink(temp.fileSystemRepresentation);
            require(linked==0 || saved==EEXIST,"Cannot publish PNG");
        }
        NSMutableDictionary *f=[currentGeometry mutableCopy]; f[@"name"]=name; f[@"capture_id"]=@(captureID); f[@"presented_ms"]=@(presented); latestFrame=f; return f;
    }
    NSString *receiptPath(NSString *id) { return join(join(dir,@"receipts"),[id stringByAppendingString:@".json"]); }
    void finish(NSString *disposition, NSString *reason, NSDictionary *frame=nil) {
        require(request!=nil,"Missing active request");
        writeJSON(receiptPath(request[@"id"]),@{@"schema":@"computer-receipt/1",@"id":request[@"id"],@"session":session,@"disposition":disposition,@"emitted_events":@(emitted),@"reason":reason,@"frame":frame?:[NSNull null]},true);
        require(unlink(join(dir,@"claimed.json").fileSystemRepresentation)==0,"Cannot retire claimed request");
        request=nil; stages.clear(); next=0; emitted=0; held.clear(); buttons=0; modifiers=KMOD_NONE; failure=nil; state();
    }
    SDL_Event key(SDL_Keycode code, bool down, SDL_Keymod mods) {
        SDL_Event e={}; e.type=down?SDL_KEYDOWN:SDL_KEYUP; e.key.timestamp=SDL_GetTicks(); e.key.windowID=windowID; e.key.state=down?SDL_PRESSED:SDL_RELEASED; e.key.keysym.sym=code; e.key.keysym.scancode=SDL_GetScancodeFromKey(code); e.key.keysym.mod=mods; return e;
    }
    void prepare(id in) {
        require([in isKindOfClass:[NSDictionary class]],"Input must be object"); NSString *type=in[@"type"];
        if([type isEqual:@"key"]) {
            require(closed(in,@[@"type",@"key",@"modifiers"]) && string(in[@"key"]),"Invalid key fields");
            SDL_Keycode code=keycode(in[@"key"]); id mods=in[@"modifiers"];
            require([mods isKindOfClass:[NSArray class]] && [mods count]<=3 && [[NSSet setWithArray:mods] count]==[mods count],"Invalid modifiers");
            for(id m in mods) require([@[@"CTRL",@"ALT",@"SHIFT"] containsObject:m],"Invalid modifier");
            std::vector<std::pair<SDL_Keycode,SDL_Keymod>> selected;
            if([mods containsObject:@"CTRL"]) selected.push_back({SDLK_LCTRL,KMOD_LCTRL});
            if([mods containsObject:@"ALT"]) selected.push_back({SDLK_LALT,KMOD_LALT});
            if([mods containsObject:@"SHIFT"]) selected.push_back({SDLK_LSHIFT,KMOD_LSHIFT});
            SDL_Keymod m=KMOD_NONE;
            for(auto item:selected) { m=(SDL_Keymod)(m|item.second); stages.push_back(key(item.first,true,m)); }
            stages.push_back(key(code,true,m));
            // SDL emits text in addition to a printable key while text input is
            // active. This is framework state, not a game/menu classification.
            if([in[@"key"] length]==1 && SDL_IsTextInputActive() &&
                    !(m & (KMOD_CTRL|KMOD_ALT))) {
                SDL_Event text={}; text.type=SDL_TEXTINPUT; text.text.windowID=windowID;
                NSString *value=in[@"key"];
                if(m & KMOD_SHIFT) value=[value uppercaseString];
                NSData *utf8=[value dataUsingEncoding:NSUTF8StringEncoding];
                require(utf8.length>0 && utf8.length<=31,"Key text outside bound");
                memcpy(text.text.text,utf8.bytes,utf8.length); stages.push_back(text);
            }
            stages.push_back(key(code,false,m));
            for(auto it=selected.rbegin();it!=selected.rend();++it) { m=(SDL_Keymod)(m&~it->second); stages.push_back(key(it->first,false,m)); }
        } else if([type isEqual:@"text"]) {
            require(closed(in,@[@"type",@"text"]) && string(in[@"text"]),"Invalid text fields"); NSString *text=in[@"text"]; NSData *utf8=[text dataUsingEncoding:NSUTF8StringEncoding];
            require(utf8 && utf8.length>0 && utf8.length<=31,"Text outside UTF8 bound");
            for(NSUInteger i=0;i<text.length;++i) { unichar c=[text characterAtIndex:i]; require(c>=32 && c!=127,"Text contains controls"); }
            SDL_Event e={}; e.type=SDL_TEXTINPUT; e.text.windowID=windowID; memcpy(e.text.text,utf8.bytes,utf8.length); stages.push_back(e);
        } else if([type isEqual:@"click"]) {
            require(closed(in,@[@"type",@"x",@"y",@"button",@"geometry"]) && geometry(in[@"geometry"]),"Invalid click fields");
            id g=in[@"geometry"]; require(number(in[@"x"],0,[g[@"width"] intValue]-1) && number(in[@"y"],0,[g[@"height"] intValue]-1) && [@[@"left",@"right"] containsObject:in[@"button"]],"Invalid click values");
            pointerGeometry(g);
            int x=(int)((long long)[in[@"x"] intValue]*[g[@"window_width"] intValue]/[g[@"width"] intValue]);
            int y=(int)((long long)[in[@"y"] intValue]*[g[@"window_height"] intValue]/[g[@"height"] intValue]);
            SDL_Event e={}; e.type=SDL_MOUSEMOTION; e.motion.windowID=windowID; e.motion.x=x; e.motion.y=y; stages.push_back(e);
            e={}; e.type=SDL_MOUSEBUTTONDOWN; e.button.windowID=windowID; e.button.button=[in[@"button"] isEqual:@"left"]?SDL_BUTTON_LEFT:SDL_BUTTON_RIGHT; e.button.state=SDL_PRESSED; e.button.clicks=1; e.button.x=x; e.button.y=y; stages.push_back(e);
            e.type=SDL_MOUSEBUTTONUP; e.button.state=SDL_RELEASED; stages.push_back(e);
        } else throw Fault("Unknown basic input");
        require(stages.size()<=8,"Event bound exceeded");
    }
    void claim() {
        NSString *pending=join(dir,@"request.json"), *claimed=join(dir,@"claimed.json");
        if(!exists(pending)) return;
        require(!exists(claimed),"Unresolved claimed request");
        if(rename(pending.fileSystemRepresentation,claimed.fileSystemRepresentation)!=0) { if(errno==ENOENT) return; throw Fault("Cannot claim request"); }
        NSData *data=regularData(claimed);
        // Single owned Python writer publishes canonical, strictly validated JSON.
        // Foundation does not independently reject duplicate JSON keys here.
        id decoded=[NSJSONSerialization JSONObjectWithData:data options:0 error:nil];
        require([decoded isKindOfClass:[NSDictionary class]] && identity(decoded[@"id"]),"Request has no valid ID");
        request=decoded; emitted=0;
        if(exists(receiptPath(request[@"id"]))) { require(unlink(claimed.fileSystemRepresentation)==0,"Cannot retire duplicate request"); request=nil; return; }
        require(closed(request,@[@"schema",@"id",@"session",@"kind",@"expires_ms",@"input"]),"Invalid request fields");
        require([request[@"schema"] isEqual:@"computer-request/1"] && [request[@"session"] isEqual:session],"Request schema/session differs");
        long long now=nowMS();
        require(number(request[@"expires_ms"],1,MaxInteger) && [request[@"expires_ms"] longLongValue]>now && [request[@"expires_ms"] longLongValue]<=now+5000,"Request expiry outside five-second bound");
        require([@[@"observe",@"input"] containsObject:request[@"kind"]],"Unknown request kind");
        if([request[@"kind"] isEqual:@"observe"]) {
            require(request[@"input"]==[NSNull null],"Observe input must be null");
            finish(@"delivered",@"Captured presented pixels",saveFrame());
        } else {
            fence(); require(!paused,"Target paused");
            require(window && renderer && !lost,"Bound target not ready"); prepare(request[@"input"]);
        }
    }
    void ownership(const SDL_Event &e) {
        if(e.type==SDL_KEYDOWN) { held.push_back(e.key.keysym.sym); modifiers=(SDL_Keymod)e.key.keysym.mod; }
        if(e.type==SDL_KEYUP) { auto i=std::find(held.begin(),held.end(),e.key.keysym.sym); if(i!=held.end()) held.erase(i); modifiers=(SDL_Keymod)e.key.keysym.mod; }
        if(e.type==SDL_MOUSEMOTION) { pointer=true; mouseX=e.motion.x; mouseY=e.motion.y; }
        if(e.type==SDL_MOUSEBUTTONDOWN) { pointer=true; buttons|=SDL_BUTTON(e.button.button); mouseX=e.button.x; mouseY=e.button.y; }
        if(e.type==SDL_MOUSEBUTTONUP) buttons&=~SDL_BUTTON(e.button.button);
    }
    void cleanup() {
        stages.clear(); next=0;
        // Release only our owned presses. No mutation of actual SDL device state.
        SDL_Keymod m=modifiers;
        for(auto it=held.rbegin();it!=held.rend();++it) {
            if(*it==SDLK_LCTRL) m=(SDL_Keymod)(m&~KMOD_LCTRL);
            if(*it==SDLK_LALT) m=(SDL_Keymod)(m&~KMOD_LALT);
            if(*it==SDLK_LSHIFT) m=(SDL_Keymod)(m&~KMOD_LSHIFT);
            stages.push_back(key(*it,false,m));
        }
        for(Uint8 b : {Uint8(SDL_BUTTON_LEFT),Uint8(SDL_BUTTON_RIGHT)}) if(buttons&SDL_BUTTON(b)) {
            SDL_Event e={}; e.type=SDL_MOUSEBUTTONUP; e.button.windowID=windowID; e.button.button=b; e.button.state=SDL_RELEASED; e.button.x=mouseX; e.button.y=mouseY; stages.push_back(e);
        }
    }
    int poll(SDL_Event *out) {
        init(); if(!enabled) return 0; fence();
        if(yieldEmpty) { yieldEmpty=false; state(); return 0; }
        if(!request) claim();
        if(!request) return 0;
        if([request[@"kind"] isEqual:@"input"]) {
            fence();
            if([request[@"expires_ms"] longLongValue]<=nowMS() && !failure) { failure=@"Request expired during dispatch"; if(emitted) pause(failure); }
            if(paused && !failure) failure=error;
            if(failure && next<stages.size()) cleanup();
            if(next<stages.size()) {
                if([request[@"input"][@"type"] isEqual:@"click"] && !failure) {
                    pointerGeometry(request[@"input"][@"geometry"]);
                }
                SDL_Event e=stages[next++]; require(emitted<8,"Event bound exceeded");
                e.common.timestamp=SDL_GetTicks(); ownership(e); ++emitted; *out=e; yieldEmpty=true; return 1;
            }
            if(failure) finish(emitted?@"partial":@"rejected",failure);
            else finish(@"delivered",@"SDL events emitted; application effect unknown");
        }
        return 0;
    }
    void physical(const SDL_Event &e) {
        if(!enabled) return;
        switch(e.type) {
            case SDL_MOUSEMOTION: if(e.motion.state) pause(@"Physical drag takeover",true); else pointer=false; break;
            case SDL_KEYDOWN: case SDL_KEYUP: case SDL_TEXTINPUT: case SDL_TEXTEDITING: case SDL_TEXTEDITING_EXT:
            case SDL_MOUSEBUTTONDOWN: case SDL_MOUSEBUTTONUP: case SDL_MOUSEWHEEL:
            case SDL_JOYAXISMOTION: case SDL_JOYBALLMOTION: case SDL_JOYHATMOTION: case SDL_JOYBUTTONDOWN: case SDL_JOYBUTTONUP:
            case SDL_CONTROLLERAXISMOTION: case SDL_CONTROLLERBUTTONDOWN: case SDL_CONTROLLERBUTTONUP:
            case SDL_CONTROLLERTOUCHPADDOWN: case SDL_CONTROLLERTOUCHPADUP: case SDL_CONTROLLERTOUCHPADMOTION:
            case SDL_FINGERDOWN: case SDL_FINGERUP: case SDL_FINGERMOTION:
                pause(@"Physical input takeover",true); break;
            case SDL_WINDOWEVENT:
                if(e.window.windowID==windowID && e.window.event==SDL_WINDOWEVENT_CLOSE) { lost=true; pause(@"Bound window closing"); }
                break;
            case SDL_QUIT: lost=true; pause(@"Application quit"); break;
        }
        state();
    }
    void fault(NSString *why) {
        error=why;
        if(request && emitted==0) { try { finish(@"rejected",why); return; } catch(...) {} }
        pause(why);
        // Keep the claimed request if storage failed: it is evidence of unknown
        // delivery. A later poll may perform only owned neutralization/collection.
        if(request && emitted) { failure=why; cleanup(); }
        try { state(); } catch(...) {}
    }
};
Bridge &bridge() { static Bridge b; return b; }
NSString *message(const std::exception &e) { return [NSString stringWithUTF8String:e.what()]?:@"Native exception"; }
void containFault(NSString *why) noexcept {
    @try {
        try {
            auto &b=bridge(); std::lock_guard<std::recursive_mutex> guard(b.mutex);
            b.fault(why);
        } catch(...) { bridge().paused=true; }
    } @catch(NSException *) { bridge().paused=true; }
}
template<class F> void guarded(F f) noexcept {
    @autoreleasepool {
        @try {
            try { f(); }
            catch(const std::exception &e) { containFault(message(e)); }
            catch(...) { containFault(@"Unknown native exception"); }
        } @catch(NSException *e) { containFault(e.reason?:@"Foundation exception"); }
    }
}
}

extern "C" void computer_present(SDL_Renderer *renderer) {
    bool presented=false;
    guarded([&] {
        auto &b=bridge(); std::lock_guard<std::recursive_mutex> guard(b.mutex);
        b.capture(renderer);
        // Keep cached pixels unavailable to observers until the real present.
        SDL_RenderPresent(renderer); presented=true;
        if(b.enabled && b.renderer==renderer && !b.lost) b.presented=nowMS();
    });
    if(!presented) SDL_RenderPresent(renderer);
}
extern "C" SDL_Renderer *computer_create_renderer(SDL_Window *window,int index,Uint32 flags) {
    SDL_Renderer *renderer=SDL_CreateRenderer(window,index,flags);
    if(renderer) guarded([&] { auto &b=bridge(); std::lock_guard<std::recursive_mutex> guard(b.mutex); b.bind(renderer); });
    return renderer;
}
extern "C" void computer_destroy_renderer(SDL_Renderer *renderer) {
    guarded([&] { auto &b=bridge(); std::lock_guard<std::recursive_mutex> guard(b.mutex); if(b.enabled && b.renderer==renderer) { b.lost=true; b.pause(@"Bound renderer destroyed"); b.state(); } });
    SDL_DestroyRenderer(renderer);
}
extern "C" void computer_destroy_window(SDL_Window *window) {
    guarded([&] { auto &b=bridge(); std::lock_guard<std::recursive_mutex> guard(b.mutex); if(b.enabled && b.window==window) { b.lost=true; b.pause(@"Bound window destroyed"); b.state(); } });
    SDL_DestroyWindow(window);
}
extern "C" int computer_poll(SDL_Event *event) {
    // Always ask the real queue first, including the explicit stage-empty call.
    int real=SDL_PollEvent(event);
    if(real) { if(event) guarded([&] { auto &b=bridge(); std::lock_guard<std::recursive_mutex> guard(b.mutex); b.init(); b.physical(*event); }); return real; }
    if(!event) return 0;
    int result=0; guarded([&] { auto &b=bridge(); std::lock_guard<std::recursive_mutex> guard(b.mutex); result=b.poll(event); }); return result;
}
extern "C" Uint32 computer_mouse(int *x,int *y) {
    Uint32 actual=SDL_GetMouseState(x,y); auto &b=bridge(); std::lock_guard<std::recursive_mutex> guard(b.mutex);
    if(b.enabled && b.pointer && !b.human && !b.paused) { if(x) *x=b.mouseX; if(y) *y=b.mouseY; return actual|b.buttons; } return actual;
}
extern "C" Uint32 computer_global_mouse(int *x,int *y) {
    Uint32 actual=SDL_GetGlobalMouseState(x,y); auto &b=bridge(); std::lock_guard<std::recursive_mutex> guard(b.mutex);
    if(b.enabled && b.pointer && !b.human && !b.paused && !b.lost) { int wx=0,wy=0; SDL_GetWindowPosition(b.window,&wx,&wy); if(x) *x=wx+b.mouseX; if(y) *y=wy+b.mouseY; return actual|b.buttons; } return actual;
}
extern "C" SDL_Keymod computer_modifiers() {
    SDL_Keymod actual=SDL_GetModState(); auto &b=bridge(); std::lock_guard<std::recursive_mutex> guard(b.mutex);
    return b.enabled && b.request && !b.human && !b.paused ? (SDL_Keymod)(actual|b.modifiers) : actual;
}
__attribute__((used,section("__DATA,__interpose")))
static const InterposeEntry computerInterpositions[] = {
    {(const void *)&computer_present,(const void *)&SDL_RenderPresent},
    {(const void *)&computer_create_renderer,(const void *)&SDL_CreateRenderer},
    {(const void *)&computer_destroy_renderer,(const void *)&SDL_DestroyRenderer},
    {(const void *)&computer_destroy_window,(const void *)&SDL_DestroyWindow},
    {(const void *)&computer_poll,(const void *)&SDL_PollEvent},
    {(const void *)&computer_mouse,(const void *)&SDL_GetMouseState},
    {(const void *)&computer_global_mouse,(const void *)&SDL_GetGlobalMouseState},
    {(const void *)&computer_modifiers,(const void *)&SDL_GetModState}
};
