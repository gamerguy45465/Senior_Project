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
    qml/*.qml

RESOURCES += \
    texteditor.qrc

target.path = $$[QT_INSTALL_EXAMPLES]/quickcontrols2/texteditor
INSTALLS += target

DISTFILES += \
    agent.py

win32 {
    # You can override this in your environment with PYTHON_HOME.
    isEmpty(PYTHON_HOME): PYTHON_HOME = $$(PYTHON_HOME)
    isEmpty(PYTHON_HOME): PYTHON_HOME = C:/Users/jorda/AppData/Local/Programs/Python/Python311
    # Optional override if your Python import library name is not python311.
    isEmpty(PYTHON_LIBRARY): PYTHON_LIBRARY = $$(PYTHON_LIBRARY)
    isEmpty(PYTHON_LIBRARY): PYTHON_LIBRARY = python311

    INCLUDEPATH += $$PYTHON_HOME/include
    LIBS += -L$$PYTHON_HOME/libs -l$$PYTHON_LIBRARY
}
