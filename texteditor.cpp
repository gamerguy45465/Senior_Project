// Copyright (C) 2017 The Qt Company Ltd.
// SPDX-License-Identifier: LicenseRef-Qt-Commercial OR BSD-3-Clause

#ifdef QT_WIDGETS_LIB
#include <QApplication>
#else
#include <QGuiApplication>
#endif
#include <QFontDatabase>
#include <QDebug>
#include <QQmlApplicationEngine>
#include <QQmlContext>
#include <QQuickStyle>
#include <QQuickTextDocument>
#include "pythonsyntaxhighlighting.h"

#include "documenthandler.h"
#include "backend.h"

int main(int argc, char *argv[])
{
    QGuiApplication::setApplicationName("Text Editor");
    QGuiApplication::setOrganizationName("QtProject");

#ifdef QT_WIDGETS_LIB
    QApplication app(argc, argv);
#else
    QGuiApplication app(argc, argv);
#endif

    if (QFontDatabase::addApplicationFont(":/fonts/fontello.ttf") == -1)
        qWarning() << "Failed to load fontello.ttf";

    qmlRegisterType<DocumentHandler>("io.qt.examples.texteditor", 1, 0, "DocumentHandler");
    qmlRegisterType<Backend>("ide.backend", 1, 0, "Backend");

    QStringList selectors;
#ifdef QT_EXTRA_FILE_SELECTOR
    selectors += QT_EXTRA_FILE_SELECTOR;
#else
    if (app.arguments().contains("-touch"))
        selectors += "touch";
#endif

    QQmlApplicationEngine engine;
    engine.setExtraFileSelectors(selectors);

    engine.load(QUrl("qrc:/qml/texteditor.qml"));
    if (engine.rootObjects().isEmpty())
        return -1;


    QObject *editor = engine.rootObjects().first()
                          ->findChild<QObject*>("editor");

    auto doc = editor->property("textDocument")
                   .value<QQuickTextDocument*>();


    new PythonSyntaxHighlighting(doc->textDocument());

    Backend terminal_backend;
    DocumentHandler terminal_dh;


    QObject::connect(&terminal_dh, &DocumentHandler::fileUrlChanged, &terminal_backend, &Backend::fileUrlChanged);


    engine.rootContext()->setContextProperty("t_backend", &terminal_backend);








    return app.exec();
}
