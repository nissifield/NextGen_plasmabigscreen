// SPDX-FileCopyrightText: 2026 Devin Lin <devin@kde.org>
// SPDX-License-Identifier: GPL-2.0-or-later

import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2

import org.kde.kirigami as Kirigami
import org.kde.bigscreen as Bigscreen

Bigscreen.ItemDelegate {
    id: root

    property var tasksModel

    signal closeHomeRequested()

    property bool delegatePressed: false
    onDelegatePressedChanged: {
        if (delegatePressed) {
            closeAnim.restart();
        } else {
            closeAnim.stop();
            closeFactor = 0;
        }
    }

    // Hold-and-close threshold
    property real closeFactor: 0
    NumberAnimation on closeFactor {
        id: closeAnim
        from: 0
        to: 1
        running: false
        duration: 1000
        onFinished: {
            tasksModel.requestClose(tasksModel.makeModelIndex(index));
        }
    }
    opacity: 1 - closeFactor

    onClicked: {
        tasksModel.minimizeAllTasks();
        tasksModel.requestActivate(tasksModel.makeModelIndex(index));
        root.closeHomeRequested();
    }

    onPressedChanged: {
        delegatePressed = pressed;
    }

    function isConfirmKey(key) {
        return key === Qt.Key_Return || key === Qt.Key_Enter || key === Qt.Key_Select || key === Qt.Key_Space;
    }

    Keys.onPressed: (event) => {
        if (event.isAutoRepeat) {
            return;
        }
        if (isConfirmKey(event.key)) {
            event.accepted = true;
            delegatePressed = true;
        } else if (event.key === Qt.Key_Delete || event.key === Qt.Key_Menu || event.key === Qt.Key_MenuKB) {
            event.accepted = true;
            tasksModel.requestClose(tasksModel.makeModelIndex(index));
        } else {
            event.accepted = false;
        }
    }
    Keys.onReleased: (event) => {
        if (event.isAutoRepeat) {
            return;
        }
        if (delegatePressed && isConfirmKey(event.key)) {
            event.accepted = true;

            // Don't "click" unless the user just pressed state was very short
            if (root.closeFactor < 0.2) {
                click();
            }
            delegatePressed = false;
        } else {
            event.accepted = false;
        }
    }

    contentItem: Item {
        ColumnLayout {
            opacity: 1 - Math.min(1, root.closeFactor * 8)
            anchors.fill: parent
            spacing: Kirigami.Units.mediumSpacing

            Kirigami.Icon {
                Layout.alignment: Qt.AlignHCenter | Qt.AlignBottom
                implicitWidth: Kirigami.Units.iconSizes.medium
                implicitHeight: Kirigami.Units.iconSizes.medium
                source: model.decoration
            }

            QQC2.Label {
                Layout.alignment: Qt.AlignTop
                Layout.fillWidth: true
                text: model.AppName
                horizontalAlignment: Text.AlignHCenter
                elide: Text.ElideRight
                font.pixelSize: Bigscreen.Units.defaultFontPixelSize
            }
        }

        ColumnLayout {
            id: closeComponent
            opacity: Math.min(1, root.closeFactor * 2)
            anchors.fill: parent
            spacing: Kirigami.Units.mediumSpacing

            Kirigami.Icon {
                id: closeIcon
                Layout.alignment: Qt.AlignHCenter | Qt.AlignBottom
                implicitWidth: Kirigami.Units.iconSizes.medium
                implicitHeight: Kirigami.Units.iconSizes.medium
                source: "tab-close"
            }

            QQC2.Label {
                Layout.alignment: Qt.AlignTop
                Layout.fillWidth: true
                horizontalAlignment: Text.AlignHCenter
                elide: Text.ElideRight
                text: i18n("Hold to close…")
                font.pixelSize: Bigscreen.Units.defaultFontPixelSize
            }
        }
    }
}
