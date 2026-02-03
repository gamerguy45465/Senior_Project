// Copyright (C) 2021 The Qt Company Ltd.
// SPDX-License-Identifier: LicenseRef-Qt-Commercial OR BSD-3-Clause

import QtQuick
import QtCore
import QtQuick.Controls
import QtQuick.Window
import QtQuick.Dialogs
import Qt.labs.platform as Platform

import io.qt.examples.texteditor
import ide.backend

// TODO:
// - make designer-friendly

ApplicationWindow {
    id: window
    width: 1024
    height: 600
    visible: true
    //title: document.fileName + " - Text Editor Example"


    property bool runPending: false
    property url runFileURL: ""
    property url runSelectedFile: ""


    function triggerRunAfterSave() {
        runPending = true



        saveDialog.open()

        doPendingRun()
    }


    function doPendingRun() {
        if(!runPending)
            return

        runPending = false


        console.log(runFileURL, runSelectedFile)




        backend.runInTerminal(runFileURL.toString(), runSelectedFile.tString())
    }

    DocumentHandler {
        id: documenthandler
    }

    Backend {
        id: backend
        onPathChanged: console.log("Path:", path)
        onDataChanged: console.log("Path:", path)
    }

    Component.onCompleted: {
        x = Screen.width / 2 - width / 2
        y = Screen.height / 2 - height / 2
    }

    Action {
        id: openAction
        shortcut: StandardKey.Open
        onTriggered: openDialog.open()
    }

    Action {
        id: saveAsAction
        shortcut: StandardKey.SaveAs
        onTriggered: saveDialog.open()
    }

    Action {
        id: runAction
        text: "Run"
        shortcut: "F5"
        onTriggered: {
            runFileUrl: documenthandler.fileUrl
            runSelectedFile: saveDialog.selectedFile
            while(!t_backend.getEmittedState())
                ;

            triggerRunAfterSave()


        }
    }

    Action {
        id: quitAction
        shortcut: StandardKey.Quit
        onTriggered: close()
    }

    Action {
        id: copyAction
        shortcut: StandardKey.Copy
        onTriggered: textArea.copy()
    }

    Action {
        id: cutAction
        shortcut: StandardKey.Cut
        onTriggered: textArea.cut()
    }

    Action {
        id: pasteAction
        shortcut: StandardKey.Paste
        onTriggered: textArea.paste()
    }

    Action {
        id: boldAction
        shortcut: StandardKey.Bold
        onTriggered: document.bold = !document.bold
    }

    Action {
        id: italicAction
        shortcut: StandardKey.Italic
        onTriggered: document.italic = !document.italic
    }

    Action {
        id: underlineAction
        shortcut: StandardKey.Underline
        onTriggered: document.underline = !document.underline
    }

    Platform.MenuBar {
        Platform.Menu {
            title: qsTr("&File")

            Platform.MenuItem {
                text: qsTr("&Open")
                onTriggered: openDialog.open()
            }
            Platform.MenuItem {
                text: qsTr("&Save As...")
                onTriggered: saveDialog.open()
            }
            Platform.MenuItem {
                text: qsTr("&Quit")
                onTriggered: close()
            }
        }

        Platform.Menu {
            title: qsTr("&Edit")

            Platform.MenuItem {
                text: qsTr("&Copy")
                //enabled: textArea.selectedText
                onTriggered: textArea.copy()
            }
            Platform.MenuItem {
                text: qsTr("Cu&t")
                //enabled: textArea.selectedText
                onTriggered: textArea.cut()
            }
            Platform.MenuItem {
                text: qsTr("&Paste")
                //enabled: textArea.canPaste
                onTriggered: textArea.paste()
            }
        }


    }

    FileDialog {
        id: openDialog
        fileMode: FileDialog.OpenFile
        selectedNameFilter.index: 1
        nameFilters: ["All files (*)"]
        currentFolder: StandardPaths.writableLocation(StandardPaths.DocumentsLocation)
        onAccepted: document.load(selectedFile)
    }

    FileDialog {
        id: saveDialog
        fileMode: FileDialog.SaveFile
        defaultSuffix: "py"

        nameFilters: [
            "Python files (*.py)",
            "Text files (*.txt)",
            "All files (*)"
        ]

        currentFolder: StandardPaths.writableLocation(StandardPaths.DocumentsLocation)

        onAccepted: {
            runSelectedFile = selectedFile
            documenthandler.saveAs(selectedFile)

        }
    }

    FontDialog {
        id: fontDialog
        onAccepted: document.font = selectedFont
    }

    ColorDialog {
        id: colorDialog
        selectedColor: "black"
        onAccepted: document.textColor = selectedColor
    }

    MessageDialog {
        title: qsTr("Error")
        id: errorDialog
    }

    MessageDialog {
        id : quitDialog
        title: qsTr("Quit?")
        text: qsTr("The file has been modified. Quit anyway?")
        buttons: MessageDialog.Yes | MessageDialog.No
        onButtonClicked: function (button, role) { if (role === MessageDialog.YesRole) Qt.quit() }
    }

    header: ToolBar {
        leftPadding: 8

        Flow {
            id: flow
            width: parent.width

            Row {
                id: fileRow
                ToolButton {
                    id: openButton
                    text: "\uF115" // icon-folder-open-empty
                    font.family: "fontello"
                    action: openAction
                    focusPolicy: Qt.TabFocus
                }
                ToolSeparator {
                    contentItem.visible: fileRow.y === editRow.y
                }
            }

            Row {
                id: editRow
                ToolButton {
                    id: runButton
                    text: "Run"
                    font.family: "fontello"
                    focusPolicy: Qt.TabFocus
                    //enabled: editor.selectedText
                    action: runAction
                }
                ToolButton {
                    id: debugButton
                    text: "Debug"
                    font.family: "fontello"
                    focusPolicy: Qt.TabFocus
                    //enabled: editor.selectedText
                }

            }


        }
    }

    ScrollView {
        anchors.fill: parent
        Rectangle {
            width: parent.width
            height: parent.height
            color: "white"
            border.color: "red"
            border.width: 2
            TextEdit{
                id: editor
                objectName: "editor"
                anchors.fill: parent
                anchors.margins: 8
                focus: true

                wrapMode: TextEdit.NoWrap



                Keys.onReturnPressed: autoIndent()

                function autoIndent() {
                    let pos = cursorPosition
                    let t = text

                    let lineStart = t.lastIndexOf("\n", pos - 1) + 1
                    let line = t.substring(lineStart, pos)


                    let m = line.match(/^\s*/)
                    let indent = m ? m[0] : ""


                    if(line.trim().endsWith(":"))
                        indent += "    "

                    let toInsert = "\n" + indent


                    text = t.substring(0, pos) + toInsert + t.substring(pos)
                    cursorPosition = pos + toInsert.length
                }


            }

        }
    }
}
