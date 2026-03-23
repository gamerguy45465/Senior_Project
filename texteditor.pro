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
    PYTHON_LIB_DIR = "C:/Users/Jordan Coleman/AppData/Local/Programs/Python/Python314/libs"
    PYTHON_LIBRARY = python314

    LIBS += -L$$PYTHON_LIB_DIR -l$$PYTHON_LIBRARY

    QMAKE_POST_LINK += copy /y \"C:/Users/Jordan Coleman/AppData/Local/Programs/Python/Python314/python314.dll\" \"$$OUT_PWD/python314.dll\"$$escape_expand(\\n\\t)
    QMAKE_POST_LINK += copy /y \"C:/Users/Jordan Coleman/AppData/Local/Programs/Python/Python314/python3.dll\" \"$$OUT_PWD/python3.dll\"$$escape_expand(\\n\\t)
}
