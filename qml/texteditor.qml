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

        // If the document already has a filename, save in-place and run.
        if (documenthandler.fileUrl && documenthandler.fileUrl.toString() !== "") {
            documenthandler.save()
            doPendingRun()
            return
        }

        // Otherwise prompt for a filename.
        saveDialog.open()
    }


    function doPendingRun() {
        if(!runPending)
            return;

        runPending = false;


        console.log(runFileURL, runSelectedFile);




        backend.runInTerminal(documenthandler.fileUrl.toString(), "");
        runSelectedFile.toString();
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
        documenthandler.document = editor.textDocument

        x = Screen.width / 2 - width / 2
        y = Screen.height / 2 - height / 2
    }

    Action {
        id: openAction
        shortcut: StandardKey.Open
        onTriggered: openDialog.open()
    }

    Action {
        id: saveAction
        shortcut: StandardKey.Save
        onTriggered: {
            if (documenthandler.fileUrl && documenthandler.fileUrl.toString() !== "") {
                documenthandler.save()
            } else {
                saveDialog.open()
            }
        }
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
        onTriggered: editor.copy()
    }

    Action {
        id: cutAction
        shortcut: StandardKey.Cut
        onTriggered: editor.cut()
    }

    Action {
        id: pasteAction
        shortcut: StandardKey.Paste
        onTriggered: editor.paste()
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
                onTriggered: editor.copy()
            }
            Platform.MenuItem {
                text: qsTr("Cu&t")
                //enabled: textArea.selectedText
                onTriggered: editor.cut()
            }
            Platform.MenuItem {
                text: qsTr("&Paste")
                //enabled: textArea.canPaste
                onTriggered: editor.paste()
            }
        }


    }

    FileDialog {
        id: openDialog
        fileMode: FileDialog.OpenFile
        selectedNameFilter.index: 1
        nameFilters: ["All files (*)"]
        currentFolder: StandardPaths.writableLocation(StandardPaths.DocumentsLocation)
        onAccepted: documenthandler.load(selectedFile)
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
            documenthandler.saveAs(selectedFile)
            // If a Run was waiting on a filename, run now.
            doPendingRun()
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
