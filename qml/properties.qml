import QtQuick
import QtCore
import QtQuick.Controls
import QtQuick.Window
import QtQuick.Layouts

import ide.backend

Window {
    id: window
    width: 1024
    height: 600
    visible: true
    title: qsTr("Properties")
    color: "#F6F6F6"

    property int selectedTab: 0

    function saveAiModel() {
        const cleaned = modelField.text.trim()
        settingsBackend.aiModel = cleaned.length > 0 ? cleaned : settingsBackend.defaultAiModel()
        modelField.text = settingsBackend.aiModel
        saveMessage.text = qsTr("Saved model: %1").arg(settingsBackend.aiModel)
        saveMessage.color = "#2E7D32"
    }

    Backend {
        id: settingsBackend
    }

    RowLayout {
        anchors.fill: parent
        spacing: 0

        Rectangle {
            Layout.preferredWidth: 220
            Layout.fillHeight: true
            color: "#E4E4E4"

            ListView {
                id: tabList
                anchors.fill: parent
                model: ["Python Interpreter", "Appearance", "AI Settings"]
                currentIndex: window.selectedTab
                interactive: false

                delegate: Rectangle {
                    width: ListView.view.width
                    height: 42
                    color: window.selectedTab === index ? "#F6F6F6" : "#E4E4E4"

                    Rectangle {
                        visible: window.selectedTab === index
                        width: 3
                        height: parent.height
                        color: "#5D5F61"
                    }

                    Text {
                        text: modelData
                        anchors.fill: parent
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                        color: "#202020"
                    }

                    MouseArea {
                        anchors.fill: parent
                        hoverEnabled: true

                        onClicked: {
                            window.selectedTab = index
                        }

                        onEntered: {
                            if (window.selectedTab !== index) {
                                parent.color = "#CDCDCD"
                            }
                        }

                        onExited: {
                            if (window.selectedTab !== index) {
                                parent.color = "#E4E4E4"
                            }
                        }
                    }
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: "#F6F6F6"

            StackLayout {
                anchors.fill: parent
                anchors.margins: 24
                currentIndex: window.selectedTab

                Item {
                    ColumnLayout {
                        anchors.fill: parent
                        spacing: 8

                        Label {
                            text: qsTr("Python Interpreter")
                            font.bold: true
                            font.pointSize: 13
                        }

                        Label {
                            text: qsTr("Interpreter settings can be added here.")
                            color: "#5D5F61"
                        }
                    }
                }

                Item {
                    ColumnLayout {
                        anchors.fill: parent
                        spacing: 8

                        Label {
                            text: qsTr("Appearance")
                            font.bold: true
                            font.pointSize: 13
                        }

                        Label {
                            text: qsTr("Appearance settings can be added here.")
                            color: "#5D5F61"
                        }
                    }
                }

                Item {
                    ColumnLayout {
                        anchors.fill: parent
                        spacing: 12

                        Label {
                            text: qsTr("AI Settings")
                            font.bold: true
                            font.pointSize: 13
                        }

                        Label {
                            text: qsTr("Model Name")
                        }

                        TextField {
                            id: modelField
                            Layout.fillWidth: true
                            text: settingsBackend.aiModel
                            placeholderText: "gpt-5.2"
                            selectByMouse: true
                            onAccepted: window.saveAiModel()
                        }

                        Label {
                            text: qsTr("Example values: gpt-5.2, gpt-4.1")
                            color: "#5D5F61"
                        }

                        RowLayout {
                            spacing: 10

                            Button {
                                text: qsTr("Save")
                                onClicked: window.saveAiModel()
                            }

                            Button {
                                text: qsTr("Reset to Default")
                                onClicked: {
                                    settingsBackend.aiModel = settingsBackend.defaultAiModel()
                                    modelField.text = settingsBackend.aiModel
                                    saveMessage.text = qsTr("Reset model to default: %1").arg(settingsBackend.aiModel)
                                    saveMessage.color = "#5D5F61"
                                }
                            }
                        }

                        Label {
                            id: saveMessage
                            text: ""
                            color: "#5D5F61"
                        }
                    }
                }
            }
        }
    }
}
