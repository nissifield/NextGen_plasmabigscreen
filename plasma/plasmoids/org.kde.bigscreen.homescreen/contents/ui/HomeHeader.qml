// SPDX-FileCopyrightText: 2015 Marco Martin <mart@kde.org>
// SPDX-FileCopyrightText: 2019 Aditya Mehra <aix.m@outlook.com>
// SPDX-FileCopyrightText: 2025 Devin Lin <devin@kde.org>
// SPDX-License-Identifier: GPL-2.0-or-later

import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as Controls
import QtQuick.Window
import Qt5Compat.GraphicalEffects

import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.kquickcontrolsaddons
import org.kde.kirigami as Kirigami
import org.kde.bigscreen as Bigscreen
import org.kde.coreaddons as KCoreAddons
import org.kde.kirigamiaddons.components as KirigamiComponents

import "launcher"
import "indicators" as Indicators

Controls.Control {
    id: root

    readonly property real largeHeight: Math.min(parent.height / 2, Kirigami.Units.gridUnit * 8)
    readonly property real shrunkHeight: Kirigami.Units.gridUnit * 5.5

    property string activeCategory: "all"
    signal categoryActivated(string category)

    readonly property bool hasFocusWithin: root.activeFocus
        || tabAll.activeFocus || tabMedia.activeFocus || tabApps.activeFocus || tabGames.activeFocus
        || searchIndicator.activeFocus || favsIndicator.activeFocus || settingsIndicator.activeFocus
        || volumeIndicator.activeFocus || batteryIndicator.activeFocus || wifiIndicator.activeFocus
        || kdeConnectIndicator.activeFocus || shutdownIndicator.activeFocus

    function selectCategory(cat) {
        if (root.activeCategory !== cat) {
            root.activeCategory = cat;
        }
        root.categoryActivated(cat);
    }

    function activeTabButton() {
        switch (root.activeCategory) {
            case "media": return tabMedia;
            case "apps": return tabApps;
            case "games": return tabGames;
            default: return tabAll;
        }
    }

    state: "large"
    states: [
        State {
            name: "large" // When the user is at the top of the homescreen
            PropertyChanges { target: clock; state: "row" }
            PropertyChanges { target: root; height: root.largeHeight }
            PropertyChanges {
                target: root
                topPadding: Kirigami.Units.gridUnit * 1.8
            }
        },
        State {
            name: "shrunk" // When the user scrolls down in the homescreen
            PropertyChanges { target: clock; state: "row" }
            PropertyChanges { target: root; height: root.shrunkHeight }
            PropertyChanges {
                target: root
                topPadding: Kirigami.Units.gridUnit * 1.4
            }
        }
    ]
    transitions: Transition {
        PropertyAnimation { target: root; property: 'height'; duration: 200; easing.type: Easing.InOutCubic }
        PropertyAnimation { target: root; property: 'topPadding'; duration: 200; easing.type: Easing.InOutCubic }
    }

    // Forward focus to active category pill tab
    onActiveFocusChanged: {
        if (activeFocus) {
            activeTabButton().forceActiveFocus();
        }
    }

    topPadding: 0
    bottomPadding: 0
    leftPadding: 0
    rightPadding: 0

    component NavPillTab: Controls.AbstractButton {
        id: pillBtn
        required property string categoryId
        readonly property bool isCurrentCategory: root.activeCategory === categoryId

        implicitHeight: Kirigami.Units.gridUnit * 2.3
        implicitWidth: pillLabel.implicitWidth + Kirigami.Units.gridUnit * 2.2

        hoverEnabled: true
        KeyNavigation.down: root.KeyNavigation.down

        onActiveFocusChanged: {
            if (activeFocus && root.activeCategory !== categoryId) {
                root.selectCategory(categoryId);
            }
        }

        onClicked: {
            Bigscreen.NavigationSoundEffects.playClickedSound();
            Bigscreen.NavigationRumble.playConfirmRumble();
            root.selectCategory(categoryId);
            if (root.KeyNavigation.down) {
                root.KeyNavigation.down.forceActiveFocus();
            }
        }

        Keys.onReturnPressed: (event) => {
            event.accepted = true;
            pillBtn.clicked();
        }
        Keys.onEnterPressed: (event) => {
            event.accepted = true;
            pillBtn.clicked();
        }
        Keys.onSelectPressed: (event) => {
            event.accepted = true;
            pillBtn.clicked();
        }
        Keys.onSpacePressed: (event) => {
            event.accepted = true;
            pillBtn.clicked();
        }

        Keys.onPressed: (event) => {
            switch (event.key) {
                case Qt.Key_Down:
                case Qt.Key_Right:
                case Qt.Key_Left:
                case Qt.Key_Tab:
                case Qt.Key_Backtab:
                    Bigscreen.NavigationSoundEffects.playMovingSound();
                    Bigscreen.NavigationRumble.playNavigationRumble();
                    break;
                default:
                    break;
            }
        }

        background: Rectangle {
            radius: height / 2
            color: {
                if (pillBtn.activeFocus) {
                    return "white";
                }
                if (pillBtn.isCurrentCategory) {
                    return Qt.rgba(1, 1, 1, 0.22);
                }
                if (pillBtn.hovered) {
                    return Qt.rgba(1, 1, 1, 0.14);
                }
                return Qt.rgba(1, 1, 1, 0.06);
            }
            border.width: pillBtn.activeFocus ? 2 : (pillBtn.isCurrentCategory ? 1 : 0)
            border.color: pillBtn.activeFocus ? Kirigami.Theme.highlightColor : Qt.rgba(1, 1, 1, 0.35)
            Behavior on color { ColorAnimation { duration: 150 } }
        }

        contentItem: Controls.Label {
            id: pillLabel
            text: pillBtn.text
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            font.pixelSize: 18
            font.weight: (pillBtn.isCurrentCategory || pillBtn.activeFocus) ? Font.DemiBold : Font.Normal
            color: pillBtn.activeFocus ? "#111318" : (pillBtn.isCurrentCategory ? "white" : Qt.rgba(1, 1, 1, 0.82))
        }
    }

    contentItem: RowLayout {
        id: rowLayout
        spacing: Kirigami.Units.largeSpacing * 2

        Kirigami.Theme.inherit: false
        Kirigami.Theme.colorSet: Kirigami.Theme.Complementary

        Indicators.Clock {
            id: clock
            Layout.alignment: Qt.AlignTop | Qt.AlignLeft
        }

        // Android TV / Google TV Top Navigation Pill Bar
        RowLayout {
            id: navPillBar
            Layout.alignment: Qt.AlignTop
            spacing: Kirigami.Units.smallSpacing * 2

            NavPillTab {
                id: tabAll
                categoryId: "all"
                text: i18n("For You")
                KeyNavigation.right: tabMedia
                KeyNavigation.tab: tabMedia
            }

            NavPillTab {
                id: tabMedia
                categoryId: "media"
                text: i18n("Watch Now")
                KeyNavigation.left: tabAll
                KeyNavigation.backtab: tabAll
                KeyNavigation.right: tabApps
                KeyNavigation.tab: tabApps
            }

            NavPillTab {
                id: tabApps
                categoryId: "apps"
                text: i18n("Apps")
                KeyNavigation.left: tabMedia
                KeyNavigation.backtab: tabMedia
                KeyNavigation.right: tabGames
                KeyNavigation.tab: tabGames
            }

            NavPillTab {
                id: tabGames
                categoryId: "games"
                text: i18n("Games")
                KeyNavigation.left: tabApps
                KeyNavigation.backtab: tabApps
                KeyNavigation.right: searchIndicator
                KeyNavigation.tab: searchIndicator
            }
        }

        Item {
            Layout.fillWidth: true
        }

        RowLayout {
            Layout.alignment: Qt.AlignTop | Qt.AlignRight
            spacing: Kirigami.Units.gridUnit

            Indicators.Search {
                id: searchIndicator
                KeyNavigation.down: root.KeyNavigation.down
                KeyNavigation.left: tabGames
                KeyNavigation.backtab: tabGames
                KeyNavigation.right: favsIndicator
                KeyNavigation.tab: favsIndicator
            }

            Indicators.Favorites {
                id: favsIndicator
                KeyNavigation.down: root.KeyNavigation.down
                KeyNavigation.left: searchIndicator
                KeyNavigation.backtab: searchIndicator
                KeyNavigation.right: settingsIndicator
                KeyNavigation.tab: settingsIndicator
            }

            Indicators.Settings {
                id: settingsIndicator
                KeyNavigation.down: root.KeyNavigation.down
                KeyNavigation.left: favsIndicator
                KeyNavigation.right: volumeIndicator
                KeyNavigation.tab: volumeIndicator
                KeyNavigation.backtab: favsIndicator
            }

            Indicators.Volume {
                id: volumeIndicator
                KeyNavigation.down: root.KeyNavigation.down
                KeyNavigation.right: batteryIndicator.visible ? batteryIndicator : wifiIndicator
                KeyNavigation.tab: batteryIndicator.visible ? batteryIndicator : wifiIndicator
                KeyNavigation.backtab: settingsIndicator
                KeyNavigation.left: settingsIndicator
            }

            Indicators.Battery {
                id: batteryIndicator
                KeyNavigation.down: root.KeyNavigation.down
                KeyNavigation.right: wifiIndicator
                KeyNavigation.tab: wifiIndicator
                KeyNavigation.backtab: volumeIndicator
                KeyNavigation.left: volumeIndicator
            }

            Indicators.Wifi {
                id: wifiIndicator
                KeyNavigation.down: root.KeyNavigation.down
                KeyNavigation.right: kdeConnectIndicator
                KeyNavigation.tab: kdeConnectIndicator
                KeyNavigation.backtab: batteryIndicator.visible ? batteryIndicator : volumeIndicator
                KeyNavigation.left: batteryIndicator.visible ? batteryIndicator : volumeIndicator
            }

            Indicators.KdeConnect {
                id: kdeConnectIndicator
                KeyNavigation.down: root.KeyNavigation.down
                KeyNavigation.right: shutdownIndicator
                KeyNavigation.tab: shutdownIndicator
                KeyNavigation.backtab: wifiIndicator
                KeyNavigation.left: wifiIndicator
            }

            Indicators.Shutdown {
                id: shutdownIndicator
                KeyNavigation.down: root.KeyNavigation.down
                KeyNavigation.backtab: kdeConnectIndicator
                KeyNavigation.left: kdeConnectIndicator
            }
        }
    }
}
