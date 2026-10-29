// Mechanical SDL boundary. No engine or widget dependencies.
#import <Foundation/Foundation.h>
#include <SDL2/SDL.h>
#include <SDL2_image/SDL_image.h>
#include <sys/file.h>
#include <sys/stat.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <fcntl.h>
#include <unistd.h>
#include <algorithm>
#include <cerrno>
#include <cmath>
#include <climits>
#include <cstdlib>
#include <cstring>
#include <cstdint>
#include <mutex>
#include <stdexcept>
#include <string>
#include <vector>
#include <unordered_set>
#include <chrono>
// The SDK may omit dyld-interposing.h. This is the two-pointer dyld ABI,
// declared locally rather than vendoring the upstream header.
// https://github.com/apple-oss-distributions/dyld/blob/main/include/mach-o/dyld-interposing.h
struct InterposeEntry { const void *substitute; const void *original; };

namespace {
struct InheritedChannel { int lock=-1, socket=-1; std::string session; };
InheritedChannel &inherited() { static InheritedChannel value; return value; }
int descriptor(const char *value) {
    if(!value || !*value) return -1;
    char *end=nullptr; errno=0; long fd=strtol(value,&end,10);
    return errno || !end || *end || fd<3 || fd>INT_MAX ? -1 : (int)fd;
}
// Validate exactly once, before application main. Never unlock a shared inherited
// open-file description: its lock must survive the custodian closing its copy.
__attribute__((constructor)) void inheritChannel() noexcept {
    const char *path=getenv("ENACTIVE_COMPUTER_LOCK_FILE"), *token=getenv("ENACTIVE_COMPUTER_SESSION");
    int lock=descriptor(getenv("ENACTIVE_COMPUTER_LOCK_FD"));
    int channel=descriptor(getenv("ENACTIVE_COMPUTER_FD"));
    // Close-on-exec applies even when a malformed launch refuses automation.
    for(int fd : {lock,channel}) if(fd>=3) {
        int flags=fcntl(fd,F_GETFD); if(flags<0 || fcntl(fd,F_SETFD,flags|FD_CLOEXEC)!=0) return;
    }
    if(lock<3 || channel<3 || lock==channel || !path || !token || strlen(token)!=32 ||
            strspn(token,"0123456789abcdef")!=32 || getenv("ENACTIVE_COMPUTER_DIR") || getenv("CDDA_HARNESS_DIR")) return;
    struct stat held={}, named={};
    if(fstat(lock,&held)!=0 || lstat(path,&named)!=0 || !S_ISREG(held.st_mode) ||
            !S_ISREG(named.st_mode) || held.st_uid!=getuid() || named.st_uid!=getuid() ||
            held.st_dev!=named.st_dev || held.st_ino!=named.st_ino) return;
    // flock on the inherited descriptor alone could acquire an unlocked file.
    // An independent startup reference must instead see the existing exclusion.
    int probe=open(path,O_RDONLY|O_NOFOLLOW|O_CLOEXEC); if(probe<0) return;
    struct stat probeStat={};
    bool same=fstat(probe,&probeStat)==0 && probeStat.st_dev==held.st_dev && probeStat.st_ino==held.st_ino;
    int result=same?flock(probe,LOCK_EX|LOCK_NB):0; int saved=errno;
    close(probe);
    if(!same || result==0 || (saved!=EWOULDBLOCK && saved!=EAGAIN) || flock(lock,LOCK_EX|LOCK_NB)!=0) return;
    int type=0; socklen_t length=sizeof type; sockaddr_un address={}; socklen_t addressLength=sizeof address;
    if(getsockopt(channel,SOL_SOCKET,SO_TYPE,&type,&length)!=0 || type!=SOCK_STREAM ||
            getsockname(channel,(sockaddr *)&address,&addressLength)!=0 || address.sun_family!=AF_UNIX) return;
    addressLength=sizeof address;
    if(getpeername(channel,(sockaddr *)&address,&addressLength)!=0 || address.sun_family!=AF_UNIX) return;
    int flags=fcntl(channel,F_GETFL), yes=1;
    if(flags<0 || fcntl(channel,F_SETFL,flags|O_NONBLOCK)!=0 ||
            setsockopt(channel,SOL_SOCKET,SO_NOSIGPIPE,&yes,sizeof yes)!=0) return;
    try { inherited().session=token; inherited().lock=lock; inherited().socket=channel; } catch(...) {}
}
constexpr size_t MaxFrame = 64 * 1024 * 1024;
constexpr long long MaxInteger = 9007199254740991LL;
struct Fault : std::runtime_error { using std::runtime_error::runtime_error; };
long long monotonicMS() { return std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now().time_since_epoch()).count(); }
long long nowMS() { return (long long)([[NSDate date] timeIntervalSince1970] * 1000.0); }
void require(bool ok, const char *why) { if (!ok) throw Fault(why); }
bool string(id value) { return [value isKindOfClass:[NSString class]]; }
bool number(id value, long long low, long long high) {
    if (![value isKindOfClass:[NSNumber class]] || CFGetTypeID((__bridge CFTypeRef)value) == CFBooleanGetTypeID() ||
            CFNumberIsFloatType((__bridge CFNumberRef)value)) return false;
    double n = [value doubleValue];
    return std::isfinite(n) && floor(n) == n && n >= low && n <= high;
}
bool closed(id value, NSArray *keys) {
    return [value isKindOfClass:[NSDictionary class]] && [value count] == [keys count] &&
        [[NSSet setWithArray:[value allKeys]] isEqual:[NSSet setWithArray:keys]];
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
    int channel=-1; NSString *session=nil, *error=@"";
    bool channelFailed=false, sendFailed=false, receiveDrained=false, dirty=true, terminalTx=false, cleaning=false;
    std::vector<Uint8> tx, rx; size_t txOffset=0, rxNeed=4;
    NSDictionary *deferredPause=nil; std::unordered_set<std::string> seen;
    long long expiresMonotonic=0;
    SDL_Renderer *renderer=nullptr; SDL_Window *window=nullptr; Uint32 windowID=0;
    uint64_t generation=0, captureID=0; long long presented=0;
    NSDictionary *currentGeometry=nil, *latestFrame=nil, *request=nil;
    int windowPixelsW=0, windowPixelsH=0;
    std::vector<Uint8> pixels; std::vector<SDL_Event> stages; size_t next=0; unsigned emitted=0;
    std::vector<SDL_Keycode> held; Uint32 buttons=0; SDL_Keymod modifiers=KMOD_NONE; int mouseX=0,mouseY=0;
    NSString *failure=nil;
    void pause(NSString *why, bool takeover=false) {
        bool changed=!paused || (takeover && !human);
        if(takeover && !human) { ++generation; human=true; }
        if(!paused) error=why;
        paused=true; dirty=dirty || changed;
        if(takeover) { pointer=false; modifiers=KMOD_NONE; }
    }
    void init() {
        if(initialized) return; initialized=true;
        if(inherited().socket<3 || inherited().lock<3) return;
        channel=inherited().socket;
        session=[NSString stringWithUTF8String:inherited().session.c_str()]; enabled=true;
    }
    void state() { dirty=true; }
    void fence() {
        if(windowID && (lost || !window || !renderer || SDL_GetWindowFromID(windowID)!=window)) pause(@"Bound target lost");
    }
    void packet(NSString *kind, NSDictionary *value, std::vector<Uint8> png={}) {
        require(tx.empty(),"Outgoing packet still pending");
        NSDictionary *header=@{@"schema":@"computer-wire/1",@"kind":kind,@"value":value,@"payload_bytes":@(png.size())};
        NSData *data=[NSJSONSerialization dataWithJSONObject:header options:0 error:nil];
        require(data && data.length>0 && data.length<=65536,"Cannot encode bounded wire header");
        uint32_t n=(uint32_t)data.length;
        std::vector<Uint8> pending; pending.reserve(4+data.length+png.size());
        for(int shift : {24,16,8,0}) pending.push_back((Uint8)(n>>shift));
        const Uint8 *bytes=(const Uint8 *)data.bytes; pending.insert(pending.end(),bytes,bytes+data.length);
        pending.insert(pending.end(),png.begin(),png.end());
        tx.swap(pending); txOffset=0; terminalTx=[kind isEqual:@"receipt"];
    }
    void schedule() {
        if(!tx.empty() || sendFailed || request) return;
        if(deferredPause) { packet(@"receipt",deferredPause); deferredPause=nil; }
        else if(dirty) {
            packet(@"state",@{@"schema":@"computer-target/2",@"session":session,@"pid":@(getpid()),@"window_id":@(windowID),@"paused":@(paused),@"takeover_generation":@(generation),@"latest_frame":latestFrame?:[NSNull null],@"error":error});
            dirty=false;
        }
    }
    void channelFault(NSString *why, bool sending=false) {
        channelFailed=true; if(sending) sendFailed=true; pause(why);
        if(request && !failure) failure=why;
        // Retain any exact unsent terminal packet; only owned releases may follow.
    }
    void flush(size_t &budget) {
        while(!tx.empty() && budget && !sendFailed) {
            ssize_t n=send(channel,tx.data()+txOffset,std::min(budget,tx.size()-txOffset),0);
            if(n<0 && (errno==EAGAIN || errno==EWOULDBLOCK)) return;
            if(n<0 && errno==EINTR) { --budget; continue; }
            if(n<=0) { channelFault(@"Native channel send failed",true); return; }
            txOffset+=(size_t)n; budget-=(size_t)n;
            if(txOffset==tx.size()) { tx.clear(); txOffset=0; terminalTx=false; }
        }
    }
    void receive(size_t &budget) {
        receiveDrained=false; unsigned packets=0;
        while(budget && packets<8 && !channelFailed) {
            Uint8 buffer[16384]; size_t size=std::min({budget,rxNeed-rx.size(),sizeof buffer});
            ssize_t n=recv(channel,buffer,size,0);
            if(n<0 && (errno==EAGAIN || errno==EWOULDBLOCK)) { receiveDrained=true; return; }
            if(n<0 && errno==EINTR) { --budget; continue; }
            if(n<=0) { channelFault(n==0?@"Native channel EOF":@"Native channel receive failed"); return; }
            budget-=(size_t)n; rx.insert(rx.end(),buffer,buffer+n);
            if(rx.size()!=rxNeed) continue;
            if(rxNeed==4) {
                uint32_t size=((uint32_t)rx[0]<<24)|((uint32_t)rx[1]<<16)|((uint32_t)rx[2]<<8)|rx[3];
                require(size>0 && size<=65536,"Wire header outside bound"); rxNeed=4+size; continue;
            }
            NSData *data=[NSData dataWithBytes:rx.data()+4 length:rx.size()-4];
            // Only the descriptor-owning Python custodian produces this JSON. It
            // validates ingress and emits canonical JSON; Foundation does not
            // independently detect duplicate object keys.
            id header=[NSJSONSerialization JSONObjectWithData:data options:0 error:nil];
            require(closed(header,@[@"schema",@"kind",@"value",@"payload_bytes"]) &&
                    [header[@"schema"] isEqual:@"computer-wire/1"] && [header[@"kind"] isEqual:@"request"] &&
                    number(header[@"payload_bytes"],0,0),"Invalid request wire header");
            id value=header[@"value"]; rx.clear(); rxNeed=4; ++packets; claim(value);
        }
    }
    void pump() {
        init(); if(!enabled) return;
        size_t budget=256*1024;
        // Receive first: Pause fences immediately even while an image is blocked.
        if(!channelFailed) receive(budget);
        flush(budget); schedule(); flush(budget);
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
    NSDictionary *saveFrame(std::vector<Uint8> &png) {
        require(captureID>0 && !pixels.empty() && currentGeometry,"No presented capture");
        png.resize(MaxFrame);
        SDL_Surface *surface=SDL_CreateRGBSurfaceWithFormatFrom(pixels.data(),[currentGeometry[@"width"] intValue],[currentGeometry[@"height"] intValue],32,[currentGeometry[@"width"] intValue]*4,SDL_PIXELFORMAT_RGBA32);
        require(surface!=nullptr,"Cannot wrap captured pixels");
        // Installed SDL_image owns PNG encoding. The fixed-capacity memory sink
        // refuses overflow; its owned bytes remain in the pending packet.
        SDL_RWops *rw=SDL_RWFromMem(png.data(),(int)png.size());
        if(!rw) { SDL_FreeSurface(surface); throw Fault("Cannot create PNG memory sink"); }
        int rc=IMG_SavePNG_RW(surface,rw,0); Sint64 size=SDL_RWtell(rw);
        SDL_RWclose(rw); SDL_FreeSurface(surface);
        require(rc==0 && size>0 && (uint64_t)size<=MaxFrame,"PNG encoding failed or exceeded bound");
        png.resize((size_t)size);
        NSMutableDictionary *f=[currentGeometry mutableCopy];
        f[@"name"]=[NSString stringWithFormat:@"frame-%llu.png",(unsigned long long)captureID];
        f[@"capture_id"]=@(captureID); f[@"presented_ms"]=@(presented); latestFrame=f; return f;
    }
    NSDictionary *receipt(NSString *id, NSString *disposition, unsigned count, NSString *reason, NSDictionary *frame=nil) {
        return @{@"schema":@"computer-receipt/2",@"id":id,@"session":session,@"disposition":disposition,@"emitted_events":@(count),@"reason":reason,@"frame":frame?:[NSNull null]};
    }
    void finish(NSString *disposition, NSString *reason, NSDictionary *frame=nil, std::vector<Uint8> png={}) {
        require(request!=nil && tx.empty(),"Cannot finish active request while packet pending");
        packet(@"receipt",receipt(request[@"id"],disposition,emitted,reason,frame),std::move(png));
        request=nil; stages.clear(); next=0; emitted=0; held.clear(); buttons=0; modifiers=KMOD_NONE; failure=nil; cleaning=false; state();
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
    void claim(id value) {
        require(closed(value,@[@"schema",@"id",@"session",@"kind",@"expires_ms",@"input"]) &&
                identity(value[@"id"]) && [value[@"schema"] isEqual:@"computer-request/2"] &&
                [value[@"session"] isEqual:session] && [@[@"observe",@"input",@"pause"] containsObject:value[@"kind"]] &&
                number(value[@"expires_ms"],1,MaxInteger),"Invalid native request");
        std::string id=[value[@"id"] UTF8String];
        require(seen.size()<65536 && seen.insert(id).second,"Duplicate request or identity capacity exhausted");
        long long remaining=[value[@"expires_ms"] longLongValue]-nowMS();
        require(remaining>0 && remaining<=5000,"Request expiry outside five-second bound");
        if([value[@"kind"] isEqual:@"pause"]) {
            require(value[@"input"]==[NSNull null],"Pause input must be null");
            pause(@"External Pause"); if(request && next<stages.size() && !failure) failure=error;
            require(!deferredPause,"Pause receipt already pending");
            deferredPause=receipt(value[@"id"],@"delivered",0,@"Permanent Pause latched"); return;
        }
        require(!request && !terminalTx && !deferredPause,"Normal request while original receipt pending");
        request=value; emitted=0; expiresMonotonic=monotonicMS()+remaining;
        if([request[@"kind"] isEqual:@"observe"]) require(request[@"input"]==[NSNull null],"Observe input must be null");
        else {
            try { fence(); require(!paused,"Target paused"); require(window && renderer && !lost,"Bound target not ready"); prepare(request[@"input"]); }
            catch(const std::exception &e) { failure=[NSString stringWithUTF8String:e.what()]; }
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
        stages.clear(); next=0; cleaning=true;
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
        pump(); if(!enabled) return 0; fence();
        if(yieldEmpty) { yieldEmpty=false; return 0; }
        if(!request) return 0;
        if([request[@"kind"] isEqual:@"observe"]) {
            if(!tx.empty() || sendFailed) return 0;
            try {
                std::vector<Uint8> png; NSDictionary *frame=saveFrame(png);
                finish(@"delivered",@"Captured presented pixels",frame,std::move(png));
            } catch(const std::exception &e) { finish(@"rejected",[NSString stringWithUTF8String:e.what()]); }
            return 0;
        }
        if(next<stages.size() && monotonicMS()>=expiresMonotonic && !failure) {
            failure=@"Request expired during dispatch"; if(emitted) pause(failure);
        }
        if(paused && next<stages.size() && !failure) failure=error;
        if(failure && !cleaning) cleanup();
        // Pending output suppresses new command events, never owned releases.
        if(next<stages.size() && (cleaning || (tx.empty() && receiveDrained))) {
            if(SDL_HasEvents(SDL_FIRSTEVENT,SDL_LASTEVENT)) return 0;
            if([request[@"input"][@"type"] isEqual:@"click"] && !failure) {
                try { pointerGeometry(request[@"input"][@"geometry"]); }
                catch(const std::exception &e) { failure=[NSString stringWithUTF8String:e.what()]; if(emitted) pause(failure); cleanup(); return 0; }
            }
            SDL_Event e=stages[next++]; require(emitted<8,"Event bound exceeded");
            e.common.timestamp=SDL_GetTicks(); ownership(e); ++emitted; *out=e; yieldEmpty=true; return 1;
        }
        if(next==stages.size() && tx.empty() && !sendFailed) {
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
        // Protocol/duplicate failures permanently fence; never create a receipt
        // under a different identity or replace an already pending terminal one.
        channelFault(why);
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
        b.pump();
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
    if(real) { if(event) guarded([&] { auto &b=bridge(); std::lock_guard<std::recursive_mutex> guard(b.mutex); b.init(); b.physical(*event); b.pump(); }); return real; }
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
