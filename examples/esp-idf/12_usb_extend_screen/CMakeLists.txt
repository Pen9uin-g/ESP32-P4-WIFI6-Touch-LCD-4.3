# The following five lines of boilerplate have to be in your project's
# CMakeLists in this exact order for cmake to work correctly
cmake_minimum_required(VERSION 3.16)

include($ENV{IDF_PATH}/tools/cmake/project.cmake)
add_compile_options(-Wno-ignored-qualifiers)
project(usb_touch_screen)

if(NOT CONFIG_UAC_AUDIO_ENABLE)
    # project() creates managed component targets; an older IDF can still compile
    # this downloaded-but-unlinked UAC target, so only it needs TinyUSB audio declarations.
    idf_component_get_property(uac_lib espressif__usb_device_uac COMPONENT_LIB)
    if(TARGET ${uac_lib})
        target_compile_definitions(${uac_lib} PRIVATE CFG_TUD_AUDIO=1)
    endif()
endif()
