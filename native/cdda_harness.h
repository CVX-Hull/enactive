#pragma once
#include <string>
#include <vector>
#include "input_enums.h"

namespace cdda_harness
{
enum class boundary_kind { normal_play, activity_poll, interrupt_confirmation, debug_prompt, menu, unsupported };
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
// Marks only the injected pause's native cancellation invocation.
class interrupt_owner
{
    public:
        interrupt_owner();
        ~interrupt_owner();
        interrupt_owner( const interrupt_owner & ) = delete;
        interrupt_owner &operator=( const interrupt_owner & ) = delete;
};
// Used only around the two pinned cancellation query_yn call sites.
class interrupt_query
{
    public:
        interrupt_query();
        ~interrupt_query();
        interrupt_query( const interrupt_query & ) = delete;
        interrupt_query &operator=( const interrupt_query & ) = delete;
    private:
        bool active;
};
// Marks only the pinned direction helper's input wait, preserving its keymap.
class direction_query
{
    public:
        direction_query();
        ~direction_query();
        direction_query( const direction_query & ) = delete;
        direction_query &operator=( const direction_query & ) = delete;
    private:
        bool active;
};
void activity_interruptible( bool value );
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
