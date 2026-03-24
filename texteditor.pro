TEMPLATE = app
TARGET = texteditor
QT += quick quickcontrols2
qtHaveModule(widgets): QT += widgets
CONFIG += c++17

cross_compile: DEFINES += QT_EXTRA_FILE_SELECTOR=\\\"touch\\\"


HEADERS += \
    documenthandler.h \
    backend.h \
    pythonsyntaxhighlighting.h \
    python_connect.h

SOURCES += \
    python_connect.cpp \
    texteditor.cpp \
    documenthandler.cpp \
    backend.cpp \
    pythonsyntaxhighlighting.cpp

OTHER_FILES += \
    qml/*.qml \
    python/*.py

RESOURCES += \
    texteditor.qrc

target.path = $$[QT_INSTALL_EXAMPLES]/quickcontrols2/texteditor
INSTALLS += target

DISTFILES += \
    python/agent.py

win32 {
    # Allow explicit override from the environment or qmake invocation:
    #   qmake "PYTHON_BIN=C:/Path/To/python.exe"
    isEmpty(PYTHON_BIN) {
        PYTHON_BIN = $$system(py -3 -c "import sys; print(sys.executable)" 2>NUL)
        PYTHON_BIN ~= s/[\\r\\n]//g
    }

    isEmpty(PYTHON_BIN) {
        PYTHON_BIN = $$system(python3 -c "import sys; print(sys.executable)" 2>NUL)
        PYTHON_BIN ~= s/[\\r\\n]//g
    }

    isEmpty(PYTHON_BIN) {
        PYTHON_BIN = $$system(python -c "import sys; print(sys.executable)" 2>NUL)
        PYTHON_BIN ~= s/[\\r\\n]//g
    }

    # Ignore Windows Store app alias stubs if they were picked up.
    contains(PYTHON_BIN, .*WindowsApps.*) {
        PYTHON_BIN =
    }

    # Fallback to common installation locations when PATH-based discovery fails.
    isEmpty(PYTHON_BIN) {
        PYTHON_CANDIDATES = $$files($$clean_path($$(LOCALAPPDATA)/Programs/Python/Python*/python.exe))
        PYTHON_CANDIDATES += $$files("C:/Program Files/Python*/python.exe")
        PYTHON_CANDIDATES += $$files("C:/Program Files (x86)/Python*/python.exe")
        PYTHON_CANDIDATES += "C:/Program Files (x86)/Microsoft Visual Studio/Shared/Python39_64/python.exe"

        for(pyCandidate, PYTHON_CANDIDATES) {
            exists($$pyCandidate) {
                PYTHON_BIN = $$pyCandidate
                break()
            }
        }
    }

    PYTHON_BIN ~= s/[\\r\\n]//g
    isEmpty(PYTHON_BIN): error("Unable to locate Python 3 interpreter. Install Python 3 or add it to PATH.")

    PYTHON_INCLUDE_DIR = $$system("\"$$PYTHON_BIN\" -c \"import pathlib, sysconfig; print(pathlib.Path(sysconfig.get_path('include')).as_posix())\"")
    PYTHON_INCLUDE_DIR ~= s/[\\r\\n]//g

    PYTHON_LIB_DIR = $$system("\"$$PYTHON_BIN\" -c \"import pathlib, sys; print(pathlib.Path(sys.base_prefix, 'libs').as_posix())\"")
    PYTHON_LIB_DIR ~= s/[\\r\\n]//g

    PYTHON_LIBRARY = $$system("\"$$PYTHON_BIN\" -c \"import sys; print('python{}{}'.format(sys.version_info[0], sys.version_info[1]))\"")
    PYTHON_LIBRARY ~= s/[\\r\\n]//g

    PYTHON_RUNTIME_DLL_NAME = $$system("\"$$PYTHON_BIN\" -c \"import sys; print('python{}{}.dll'.format(sys.version_info[0], sys.version_info[1]))\"")
    PYTHON_RUNTIME_DLL_NAME ~= s/[\\r\\n]//g

    PYTHON_RUNTIME_DLL = $$system("\"$$PYTHON_BIN\" -c \"import pathlib, sys; print((pathlib.Path(sys.executable).resolve().parent / ('python{}{}.dll'.format(sys.version_info[0], sys.version_info[1]))).as_posix())\"")
    PYTHON_RUNTIME_DLL ~= s/[\\r\\n]//g

    PYTHON_ABI_DLL = $$system("\"$$PYTHON_BIN\" -c \"import pathlib, sys; print((pathlib.Path(sys.executable).resolve().parent / 'python3.dll').as_posix())\"")
    PYTHON_ABI_DLL ~= s/[\\r\\n]//g

    !exists("$$PYTHON_INCLUDE_DIR/Python.h"): error("Detected Python include dir does not contain Python.h: $$PYTHON_INCLUDE_DIR")
    !exists("$$PYTHON_LIB_DIR"): error("Detected Python lib dir does not exist: $$PYTHON_LIB_DIR")

    message("Using PYTHON_BIN=$$PYTHON_BIN")
    message("Using PYTHON_INCLUDE_DIR=$$PYTHON_INCLUDE_DIR")
    message("Using PYTHON_LIB_DIR=$$PYTHON_LIB_DIR")
    message("Using PYTHON_LIBRARY=$$PYTHON_LIBRARY")

    INCLUDEPATH += "$$PYTHON_INCLUDE_DIR"
    msvc:QMAKE_CXXFLAGS += /I\"$$PYTHON_INCLUDE_DIR\"
    win32-g++:QMAKE_CXXFLAGS += -I\"$$PYTHON_INCLUDE_DIR\"
    LIBS += -L"$$PYTHON_LIB_DIR" -l$$PYTHON_LIBRARY

    CONFIG(debug, debug|release) {
        PYTHON_DLL_DEST_DIR = $$clean_path($$OUT_PWD/debug)
    } else {
        PYTHON_DLL_DEST_DIR = $$clean_path($$OUT_PWD/release)
    }
    message("Using PYTHON_DLL_DEST_DIR=$$PYTHON_DLL_DEST_DIR")

    exists($$PYTHON_RUNTIME_DLL) {
        QMAKE_POST_LINK += cmd /c copy /y \"$$PYTHON_RUNTIME_DLL\" \"$$PYTHON_DLL_DEST_DIR/$$PYTHON_RUNTIME_DLL_NAME\"$$escape_expand(\\n\\t)
        QMAKE_POST_LINK += cmd /c copy /y \"$$PYTHON_RUNTIME_DLL\" \"$$OUT_PWD/$$PYTHON_RUNTIME_DLL_NAME\"$$escape_expand(\\n\\t)
    }

    exists($$PYTHON_ABI_DLL) {
        QMAKE_POST_LINK += cmd /c copy /y \"$$PYTHON_ABI_DLL\" \"$$PYTHON_DLL_DEST_DIR/python3.dll\"$$escape_expand(\\n\\t)
        QMAKE_POST_LINK += cmd /c copy /y \"$$PYTHON_ABI_DLL\" \"$$OUT_PWD/python3.dll\"$$escape_expand(\\n\\t)
    }
}
