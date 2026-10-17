#pragma once
#include <string>
#include <vector>
#include "input_enums.h"

namespace cdda_harness
{
enum class boundary_kind { normal_play, activity_poll, debug_prompt, menu, unsupported };
// Game-thread-only stack. Destruction restores the caller even during unwinding.
class scope
{
    public:
        explicit scope( boundary_kind kind );
        scope( const std::string &name, const std::vector<std::string> &actions );
        ~scope();
        scope( const scope & ) = delete;
        scope &operator=( const scope & ) = delete;
};
void playing( bool value );
void boundary();
bool poll( keyboard_mode mode, input_event &event );
void human_input();
bool enabled();
void capture_frame();
void frame_presented( bool valid );
bool write_frame( const std::string &filename );
void feed_imgui( const input_event &event );
}
