#pragma once
#include <string>
#include <vector>
#include "input_enums.h"

namespace cdda_harness
{
void context( const std::string &name, const std::vector<std::string> &actions );
void clear_context();
void playing( bool value );
void boundary();
bool poll( keyboard_mode mode, input_event &event );
void human_input();
bool enabled();
void capture_frame();
bool write_frame( const std::string &filename );
// Implemented beside the SDL/ImGui input adapter, never sends OS events.
void feed_imgui( const input_event &event );
}
