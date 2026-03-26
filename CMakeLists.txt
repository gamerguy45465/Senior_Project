cmake_minimum_required(VERSION 3.16)
project(texteditor LANGUAGES CXX)

set(CMAKE_AUTOMOC ON)

if(NOT DEFINED INSTALL_EXAMPLESDIR)
    set(INSTALL_EXAMPLESDIR "examples")
endif()

set(INSTALL_EXAMPLEDIR "${INSTALL_EXAMPLESDIR}/quickcontrols2/texteditor")

find_package(Qt6 REQUIRED COMPONENTS Core Gui Quick QuickControls2 OPTIONAL_COMPONENTS Widgets)
find_package(Python3 REQUIRED COMPONENTS Interpreter Development)

qt_add_executable(texteditorexample WIN32 MACOSX_BUNDLE
    documenthandler.cpp
    documenthandler.h
    texteditor.cpp
    pythonsyntaxhighlighting.cpp
    pythonsyntaxhighlighting.h
    backend.cpp
    backend.h
    python_connect.cpp
    python_connect.h
    python/agent.py
)

qt_add_qml_module(texteditorexample
    URI texteditor
    VERSION 1.0
    NO_RESOURCE_TARGET_PATH
    QML_FILES
        "qml/+touch/texteditor.qml"
        "qml/texteditor.qml"
        "qml/properties.qml"
        "qml/Sidebar.qml"
    RESOURCES
        "texteditor.html"
        "+touch/texteditor.html"
        "fonts/fontello.ttf"
        "images/qt-logo.png"
)

target_link_libraries(texteditorexample PUBLIC
    Qt::Core
    Qt::Gui
    Qt::Quick
    Qt::QuickControls2
    Python3::Python
)

target_compile_definitions(texteditorexample PRIVATE
    TEXTEDITOR_SOURCE_DIR=\"${CMAKE_SOURCE_DIR}\"
)

target_include_directories(texteditorexample PRIVATE
    ${Python3_INCLUDE_DIRS}
)

if(WIN32)
    get_filename_component(PYTHON_RUNTIME_DIR "${Python3_EXECUTABLE}" DIRECTORY)
    set(PYTHON_RUNTIME_DLL_NAME "python${Python3_VERSION_MAJOR}${Python3_VERSION_MINOR}.dll")
    set(PYTHON_RUNTIME_DLL "${PYTHON_RUNTIME_DIR}/${PYTHON_RUNTIME_DLL_NAME}")
    set(PYTHON_ABI_DLL "${PYTHON_RUNTIME_DIR}/python3.dll")

    if(EXISTS "${PYTHON_RUNTIME_DLL}")
        add_custom_command(TARGET texteditorexample POST_BUILD
            COMMAND ${CMAKE_COMMAND} -E copy_if_different
                "${PYTHON_RUNTIME_DLL}"
                "$<TARGET_FILE_DIR:texteditorexample>/${PYTHON_RUNTIME_DLL_NAME}"
        )
    endif()

    if(EXISTS "${PYTHON_ABI_DLL}")
        add_custom_command(TARGET texteditorexample POST_BUILD
            COMMAND ${CMAKE_COMMAND} -E copy_if_different
                "${PYTHON_ABI_DLL}"
                "$<TARGET_FILE_DIR:texteditorexample>/python3.dll"
        )
    endif()
endif()

if(TARGET Qt::Widgets)
    target_link_libraries(texteditorexample PUBLIC
        Qt::Widgets
    )
endif()

if(CMAKE_CROSSCOMPILING)
    target_compile_definitions(texteditorexample PUBLIC
        QT_EXTRA_FILE_SELECTOR="touch"
    )
endif()

install(TARGETS texteditorexample
    RUNTIME DESTINATION "${INSTALL_EXAMPLEDIR}"
    BUNDLE DESTINATION "${INSTALL_EXAMPLEDIR}"
    LIBRARY DESTINATION "${INSTALL_EXAMPLEDIR}"
)
