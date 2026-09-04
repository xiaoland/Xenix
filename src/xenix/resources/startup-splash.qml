import QtQuick

Rectangle {
    id: splash

    width: 680
    height: 400
    color: "#f1f3ee"
    property string stageText: ""

    gradient: Gradient {
        GradientStop { position: 0.0; color: "#fbfbf8" }
        GradientStop { position: 0.58; color: "#f1f3ee" }
        GradientStop { position: 1.0; color: "#dfe5dd" }
    }

    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0.0; color: "#20ed6609" }
            GradientStop { position: 0.42; color: "transparent" }
        }
    }

    Repeater {
        model: 6
        Rectangle {
            required property int index
            x: 210
            y: 42 + index * 37
            width: 428
            height: 1
            color: "#1a242429"
        }
    }

    Rectangle {
        x: 504
        y: 99
        width: 87
        height: 1
        rotation: 37
        transformOrigin: Item.Left
        color: "#30242429"
    }
    Rectangle {
        x: 566
        y: 119
        width: 92
        height: 1
        rotation: -28
        transformOrigin: Item.Left
        color: "#30242429"
    }
    Rectangle {
        x: 628
        y: 126
        width: 108
        height: 1
        rotation: 107
        transformOrigin: Item.Left
        color: "#30242429"
    }

    Repeater {
        model: [
            { "x": 446, "y": 74, "color": "#7a242429" },
            { "x": 514, "y": 126, "color": "#7aed6609" },
            { "x": 590, "y": 88, "color": "#7a242429" },
            { "x": 558, "y": 190, "color": "#7a1f7a68" }
        ]
        Rectangle {
            required property var modelData
            x: modelData.x - 4.5
            y: modelData.y - 4.5
            width: 9
            height: 9
            radius: 4.5
            color: modelData.color
        }
    }

    Rectangle {
        x: 504
        y: 42
        width: 116
        height: 12
        radius: 6
        color: "#12ed6609"
    }
    Rectangle {
        x: 544
        y: 214
        width: 78
        height: 12
        radius: 6
        color: "#12ed6609"
    }

    Image {
        x: 48
        y: 56
        width: 138
        height: 138
        source: "app-icon.svg"
        fillMode: Image.PreserveAspectFit
        asynchronous: false
    }

    Text {
        x: 208
        y: 62
        width: 300
        height: 94
        text: "Xenix"
        color: "#242429"
        verticalAlignment: Text.AlignVCenter
        font.family: "Consolas"
        font.pointSize: 54
        font.bold: true
    }

    Text {
        x: 42
        y: 338
        width: 596
        height: 22
        text: splash.stageText
        color: "#242429"
        verticalAlignment: Text.AlignVCenter
        font.family: "Segoe UI"
        font.pointSize: 10
        font.bold: true
    }

    Rectangle {
        x: 42
        y: 370
        width: 596
        height: 8
        radius: 4
        color: "#d9ded6"

        Item {
            anchors.fill: parent
            clip: true

            Rectangle {
                id: pulse
                x: -143
                width: 143
                height: 8
                radius: 4
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0.0; color: "#58ed6609" }
                    GradientStop { position: 0.5; color: "#ed6609" }
                    GradientStop { position: 1.0; color: "#58ed6609" }
                }
            }

            XAnimator {
                target: pulse
                from: -143
                to: 596
                duration: 1056
                loops: Animation.Infinite
                running: true
            }
        }
    }

    Rectangle {
        anchors.fill: parent
        color: "transparent"
        border.width: 1
        border.color: "#36242429"
    }
}
