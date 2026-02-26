import QtQuick
import QtCore
import QtQuick.Controls
import QtQuick.Window
import QtQuick.Dialogs
import Qt.labs.platform as Platform

import io.qt.examples.texteditor
import ide.backend



Window {
    id: window
    width: 1024
    height: 600
    visible: true

    Column {
        Sidebar{
            Rectangle {
                id: left_border1
                visible: false 
                width: 3
                height: 30
                color: "#5D5F61"
            }
            Text {
                text: "Python Interpreter"
                anchors.fill: parent
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment : Text.AlignVCenter
                visible: true 
            }
            MouseArea
            {
                id: mouseArea1
                anchors.fill: parent
                hoverEnabled: true 

                onEntered: {
                    parent.color = "#CDCDCD"

                }
                onClicked: {
                    parent.color = "#F6F6F6"
                    left_border1.visible = true

                    left_border2.visible = false
                }
                onExited: {
                    parent.color = "#E4E4E4"
                }

            }
        }
        Sidebar{
            Rectangle {
                id: left_border2
                visible: false 
                width: 3
                height: 30
                color: "#5D5F61"
            }
            Text {
                text: "Appearance"
                anchors.fill: parent
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment : Text.AlignVCenter
                visible: true 
            }
            MouseArea
            {
                id: mouseArea2
                anchors.fill: parent
                hoverEnabled: true 

                onEntered: {
                    parent.color = "#CDCDCD"

                }
                onClicked: {
                    parent.color = "#F6F6F6"
                    left_border2.visible = true


                    left_border1.visible = false
                }
                onExited: {
                    parent.color = "#E4E4E4"
                }

            }
        }

    }

}