TEMPLATE = app
TARGET = texteditor
QT += quick quickcontrols2
qtHaveModule(widgets): QT += widgets

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
    # You can override this in your environment with PYTHON_HOME.
    isEmpty(PYTHON_HOME): PYTHON_HOME = $$(PYTHON_HOME)
    #isEmpty(PYTHON_HOME): PYTHON_HOME = C:/Users/jorda/AppData/Local/Programs/Python/Python311
    isEmpty(PYTHON_HOME): PYTHON_HOME = C:/Python314
    # Optional override if your Python import library name is not python311.
    isEmpty(PYTHON_LIBRARY): PYTHON_LIBRARY = $$(PYTHON_LIBRARY)
    #isEmpty(PYTHON_LIBRARY): PYTHON_LIBRARY = python311
    isEmpty(PYTHON_LIBRARY): PYTHON_LIBRARY = python314

    INCLUDEPATH += $$PYTHON_HOME/include
    LIBS += -L$$PYTHON_HOME/libs -l$$PYTHON_LIBRARY

    # Make sure the Python runtime DLLs are present next to the executable.
    PYTHON_RUNTIME_DLL = $$PYTHON_HOME/python314.dll
    PYTHON_ABI_DLL = $$PYTHON_HOME/python3.dll
    OUT_PWD_WIN = $$replace(OUT_PWD, /, \\)
    PYTHON_RUNTIME_DLL_WIN = $$replace(PYTHON_RUNTIME_DLL, /, \\)
    PYTHON_ABI_DLL_WIN = $$replace(PYTHON_ABI_DLL, /, \\)

    exists($$PYTHON_RUNTIME_DLL) {
        QMAKE_POST_LINK += $$quote($$QMAKE_COPY_FILE "$$PYTHON_RUNTIME_DLL_WIN" "$$OUT_PWD_WIN\\python314.dll")$$escape_expand(\\n\\t)
    }
    exists($$PYTHON_ABI_DLL) {
        QMAKE_POST_LINK += $$quote($$QMAKE_COPY_FILE "$$PYTHON_ABI_DLL_WIN" "$$OUT_PWD_WIN\\python3.dll")$$escape_expand(\\n\\t)
    }
}
