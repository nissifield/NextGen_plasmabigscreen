// SPDX-FileCopyrightText: 2015 Marco Martin <mart@kde.org>
// SPDX-FileCopyrightText: 2019 Aditya Mehra <aix.m@outlook.com>
// SPDX-FileCopyrightText: 2025 Devin Lin <devin@kde.org>
// SPDX-License-Identifier: GPL-2.0-or-later

import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as Controls
import QtQuick.Window

import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.kquickcontrolsaddons
import org.kde.kirigami as Kirigami
import org.kde.bigscreen as Bigscreen

import "launcher"

Item {
    id: root

    readonly property real leftMargin: Kirigami.Units.gridUnit * 4
    readonly property real rightMargin: leftMargin

    // Whether to blur the wallpaper background
    readonly property bool blurBackground: launcher.scrolledDown || root.Window.activeFocusItem === null
    readonly property bool darkenBackground: launcher.scrolledDown

    property real zoomScale: 1

    function focusLauncher() {
        launcher.forceActiveFocus();
    }

    function handleBack() {
        if (launcher.closeContextMenuIfOpen()) {
            return true;
        }
        if (header.hasFocusWithin) {
            launcher.forceActiveFocus();
            return true;
        }
        return false;
    }

    Keys.onPressed: (event) => {
        if (event.key === Qt.Key_Backspace) {
            event.accepted = true;
            Bigscreen.NavigationRumble.playNavigationRumble();
            if (!root.handleBack()) {
                Plasmoid.openHomeOverlay();
            }
        } else if (event.key === Qt.Key_Search || event.key === Qt.Key_Find) {
            event.accepted = true;
            Plasmoid.openSearch();
        }
    }

    transform: Scale {
        origin.x: root.width / 2;
        origin.y: root.height / 2;
        xScale: root.zoomScale
        yScale: root.zoomScale
    }

    state: root.Window.activeFocusItem !== null ? "focused" : "unfocused"
    states: [
        State {
            name: "focused"

            PropertyChanges {
                target: root
                opacity: 1
                zoomScale: 1
            }
            StateChangeScript {
                script: Qt.callLater(() => {
                    if (root.Window.activeFocusItem !== null && !header.hasFocusWithin && !launcher.contextMenuOpen) {
                        launcher.forceActiveFocus();
                    }
                })
            }
        },
        State {
            name: "unfocused"

            PropertyChanges {
                target: root
                opacity: 1
                zoomScale: 1
            }
            StateChangeScript {
                // HACK: Kill xwaylandvideobridge if running - it interferes with bigscreen's focus
                script: Plasmoid.executeCommand("pkill -f xwaylandvideobridge")
            }
        }
    ]

    Component.onCompleted: {
        Qt.callLater(() => {
            launcher.forceActiveFocus();
        });
    }

    transitions: [
        Transition {
            to: "focused"
            ParallelAnimation {
                OpacityAnimator { duration: 300 }
                NumberAnimation { target: root; property: 'zoomScale'; duration: 600; easing.type: Easing.OutExpo }
            }
        }
    ]

    // Android TV / Google TV Dynamic Hero Spotlight Banner
    Item {
        id: heroBanner
        anchors {
            top: parent.top
            topMargin: Kirigami.Units.gridUnit * 5.0
            left: parent.left
            right: parent.right
            leftMargin: root.leftMargin
            rightMargin: root.rightMargin
        }
        height: Kirigami.Units.gridUnit * 12.2

        readonly property var app: launcher.focusedApp ?? ({
            name: "YouTube TV",
            subtitle: "Ad-Free YouTube Leanback TV Experience",
            iconName: "rocks.shy.VacuumTube",
            storageId: "rocks.shy.VacuumTube.desktop",
            running: false,
            category: "FEATURED"
        })

        readonly property string matchKey: ((app.storageId ?? "") + " " + (app.name ?? "")).toLowerCase()

        readonly property color primaryAccent: {
            if (matchKey.indexOf("vacuumtube") !== -1 || matchKey.indexOf("youtube") !== -1) {
                return "#a30b1d"; // Rich YouTube Crimson
            }
            if (matchKey.indexOf("stremio") !== -1) {
                return "#5b2c98"; // Deep Stremio Violet
            }
            if (matchKey.indexOf("jellyfin") !== -1) {
                return "#0068a8"; // Jellyfin Ocean Blue / Indigo
            }
            if (matchKey.indexOf("steam") !== -1 || matchKey.indexOf("lutris") !== -1 || matchKey.indexOf("heroic") !== -1) {
                return "#1b4b78"; // Dark Steel Blue
            }
            if (matchKey.indexOf("haruna") !== -1 || matchKey.indexOf("vlc") !== -1 || matchKey.indexOf("mpv") !== -1 || matchKey.indexOf("kodi") !== -1) {
                return "#0e6b68"; // Vibrant Media Teal
            }
            if (matchKey.indexOf("return-to-desktop") !== -1 || matchKey.indexOf("desktop mode") !== -1) {
                return "#1d5c96"; // KDE Plasma Breeze Sapphire
            }
            return Qt.darker(Kirigami.Theme.highlightColor, 1.45);
        }

        readonly property color secondaryAccent: {
            if (matchKey.indexOf("vacuumtube") !== -1 || matchKey.indexOf("youtube") !== -1) {
                return "#38060e";
            }
            if (matchKey.indexOf("stremio") !== -1) {
                return "#241145";
            }
            if (matchKey.indexOf("jellyfin") !== -1) {
                return "#162152";
            }
            if (matchKey.indexOf("steam") !== -1 || matchKey.indexOf("lutris") !== -1 || matchKey.indexOf("heroic") !== -1) {
                return "#142236";
            }
            if (matchKey.indexOf("haruna") !== -1 || matchKey.indexOf("vlc") !== -1 || matchKey.indexOf("mpv") !== -1 || matchKey.indexOf("kodi") !== -1) {
                return "#10323e";
            }
            if (matchKey.indexOf("return-to-desktop") !== -1 || matchKey.indexOf("desktop mode") !== -1) {
                return "#0f2a4a";
            }
            return Qt.darker(Kirigami.Theme.backgroundColor, 1.25);
        }

        opacity: (launcher.scrolledDown || header.forceShrunk) ? 0 : 1
        visible: opacity > 0.01
        Behavior on opacity { NumberAnimation { duration: 260; easing.type: Easing.OutCubic } }

        Rectangle {
            id: heroCard
            anchors.fill: parent
            radius: Kirigami.Units.cornerRadius * 3
            border.width: 2
            border.color: Qt.rgba(1, 1, 1, 0.22)

            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop {
                    position: 0.0
                    color: heroBanner.primaryAccent
                    Behavior on color { ColorAnimation { duration: 300 } }
                }
                GradientStop {
                    position: 0.62
                    color: heroBanner.secondaryAccent
                    Behavior on color { ColorAnimation { duration: 300 } }
                }
                GradientStop {
                    position: 1.0
                    color: Qt.rgba(0.05, 0.06, 0.09, 0.96)
                }
            }

            RowLayout {
                anchors {
                    fill: parent
                    leftMargin: Kirigami.Units.gridUnit * 2.2
                    rightMargin: Kirigami.Units.gridUnit * 2.5
                    topMargin: Kirigami.Units.gridUnit * 1.3
                    bottomMargin: Kirigami.Units.gridUnit * 1.3
                }
                spacing: Kirigami.Units.gridUnit * 2

                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    spacing: Kirigami.Units.smallSpacing * 1.5

                    // Category Pill & Running Status Row
                    RowLayout {
                        spacing: Kirigami.Units.largeSpacing

                        Rectangle {
                            radius: height / 2
                            color: Qt.rgba(1, 1, 1, 0.18)
                            border.width: 1
                            border.color: Qt.rgba(1, 1, 1, 0.35)
                            implicitHeight: Kirigami.Units.gridUnit * 1.5
                            implicitWidth: catBadgeLabel.implicitWidth + Kirigami.Units.gridUnit * 1.4

                            Controls.Label {
                                id: catBadgeLabel
                                anchors.centerIn: parent
                                text: (heroBanner.app.category && heroBanner.app.category.length > 0) ? heroBanner.app.category : i18n("FEATURED")
                                font.pixelSize: 12
                                font.weight: Font.Bold
                                font.letterSpacing: 1.1
                                color: "white"
                            }
                        }

                        Rectangle {
                            visible: Boolean(heroBanner.app.running)
                            radius: height / 2
                            color: Qt.rgba(0.12, 0.78, 0.38, 0.25)
                            border.width: 1
                            border.color: "#2ecc71"
                            implicitHeight: Kirigami.Units.gridUnit * 1.5
                            implicitWidth: runningBadgeLabel.implicitWidth + Kirigami.Units.gridUnit * 1.4

                            Controls.Label {
                                id: runningBadgeLabel
                                anchors.centerIn: parent
                                text: i18n("● RUNNING")
                                font.pixelSize: 12
                                font.weight: Font.Bold
                                color: "#4cd137"
                            }
                        }
                    }

                    Controls.Label {
                        Layout.fillWidth: true
                        text: (heroBanner.app.name && heroBanner.app.name.length > 0) ? heroBanner.app.name : i18n("Android TV Home")
                        font.pixelSize: 38
                        font.weight: Font.Bold
                        color: "white"
                        elide: Text.ElideRight
                        maximumLineCount: 1
                    }

                    Controls.Label {
                        Layout.fillWidth: true
                        text: (heroBanner.app.subtitle && heroBanner.app.subtitle.length > 0)
                            ? heroBanner.app.subtitle
                            : i18n("Press OK to launch in fullscreen 10-foot TV mode")
                        font.pixelSize: 18
                        color: Qt.rgba(1, 1, 1, 0.86)
                        elide: Text.ElideRight
                        maximumLineCount: 2
                    }

                    Item {
                        Layout.fillHeight: true
                    }

                    // Android TV Action Hint Bar
                    RowLayout {
                        spacing: Kirigami.Units.largeSpacing

                        Rectangle {
                            radius: Kirigami.Units.cornerRadius
                            color: Qt.rgba(1, 1, 1, 0.14)
                            implicitHeight: Kirigami.Units.gridUnit * 1.7
                            implicitWidth: actionHintLabel.implicitWidth + Kirigami.Units.gridUnit * 1.4

                            Controls.Label {
                                id: actionHintLabel
                                anchors.centerIn: parent
                                text: heroBanner.app.running
                                    ? i18n("[OK] Resume App   •   [Hold OK / Menu] App Options (Pin / Move / Force Stop)")
                                    : i18n("[OK] Launch   •   [Hold OK / Menu] App Options (Pin / Move / Force Stop)")
                                font.pixelSize: 13
                                font.weight: Font.Medium
                                color: Qt.rgba(1, 1, 1, 0.92)
                            }
                        }
                    }
                }

                // Right Spotlight App Icon Medallion
                Rectangle {
                    Layout.alignment: Qt.AlignVCenter | Qt.AlignRight
                    width: Kirigami.Units.gridUnit * 7.8
                    height: width
                    radius: Kirigami.Units.cornerRadius * 3
                    color: Qt.rgba(1, 1, 1, 0.10)
                    border.width: 1
                    border.color: Qt.rgba(1, 1, 1, 0.24)

                    Kirigami.Icon {
                        anchors.centerIn: parent
                        width: Kirigami.Units.gridUnit * 5.6
                        height: width
                        source: (heroBanner.app.iconName && heroBanner.app.iconName !== "")
                            ? heroBanner.app.iconName
                            : "applications-multimedia"
                    }
                }
            }
        }
    }

    HomeHeader {
        id: header
        z: 3
        anchors {
            top: parent.top
            left: parent.left
            right: parent.right
            leftMargin: root.leftMargin
            rightMargin: root.rightMargin
        }

        // Short screens don't have room for the hero banner above the first row
        readonly property bool forceShrunk: (root.height < Kirigami.Units.gridUnit * 40) || (root.width < Kirigami.Units.gridUnit * 50)
        state: (launcher.scrolledDown || forceShrunk) ? "shrunk" : "large"

        onCategoryActivated: (cat) => {
            launcher.selectCategory(cat);
        }

        KeyNavigation.down: launcher
        KeyNavigation.tab: launcher
    }

    // Application rows
    LauncherMenu {
        id: launcher
        anchors {
            fill: parent
            topMargin: header.shrunkHeight
        }

        activeCategory: header.activeCategory
        leftMargin: root.leftMargin
        rightMargin: root.rightMargin
        startY: {
            const minY = header.forceShrunk ? header.shrunkHeight : (Kirigami.Units.gridUnit * 18.8);
            const desiredY = Math.round(parent.height * 0.39);
            return Math.round(Math.max(minY, desiredY) - header.shrunkHeight);
        }

        KeyNavigation.backtab: header
        KeyNavigation.up: header
    }
}
