/*
    SPDX-FileCopyrightText: 2019 Aditya Mehra <aix.m@outlook.com>
    SPDX-FileCopyrightText: 2015 Marco Martin <mart@kde.org>

    SPDX-License-Identifier: GPL-2.0-or-later
*/

import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as Controls
import QtQuick.Window

import org.kde.plasma.plasmoid
import org.kde.kquickcontrolsaddons
import org.kde.kirigami as Kirigami
import org.kde.kitemmodels as KItemModels

import "delegates" as Delegates
import org.kde.bigscreen as Bigscreen
import org.kde.private.biglauncher 1.0
import org.kde.plasma.private.kicker 0.1 as Kicker
import org.kde.taskmanager as TaskManager

FocusScope {
    id: root

    property Item navigationUp
    property real startY
    property string activeCategory: "all"

    property var focusedApp: ({
        name: "YouTube TV",
        subtitle: "Ad-Free YouTube Leanback TV Experience",
        iconName: "rocks.shy.VacuumTube",
        storageId: "rocks.shy.VacuumTube.desktop",
        running: false,
        category: "FAVORITE"
    })

    // Emitted when an app's card is held
    signal optionsRequested(var app, Item mover)

    // Whether the view has scrolled down at least one row
    readonly property bool scrolledDown: launcherHomeColumn.currentSection && launcherHomeColumn.currentSection !== favAppsView.currentViewDownwards

    function updateFocusedApp(name: string, subtitle: string, iconName: string, storageId: string, category: string) {
        if (!name && !storageId) {
            return;
        }
        let resolvedIcon = iconName;
        if (!resolvedIcon && storageId) {
            const m = findAppItemMap(storageId);
            if (m && m.icon) {
                resolvedIcon = m.icon;
            }
        }
        root.focusedApp = {
            name: name || "",
            subtitle: subtitle || i18n("Press OK to launch in fullscreen 10-foot TV mode"),
            iconName: resolvedIcon || "applications-multimedia",
            storageId: storageId || "",
            running: root.isRunning(storageId || ""),
            category: category || i18n("FEATURED")
        };
    }

    function selectCategory(cat: string) {
        root.activeCategory = cat;
        Qt.callLater(() => {
            if (cat === "media" && mediaView.visible) {
                launcherHomeColumn.currentSection = mediaView;
            } else {
                launcherHomeColumn.currentSection = favAppsView.currentViewDownwards;
            }
            launcherHomeColumn.y = Qt.binding(() => launcherHomeColumn.intendedY());
        });
    }

    function findFavIndex(storageId: string): int {
        if (!storageId) {
            return -1;
        }
        const count = Plasmoid.favsListModel.count ?? 0;
        for (let i = 0; i < count; ++i) {
            const m = Plasmoid.favsListModel.itemMap(i);
            if (m && (m.storageId === storageId || (m.desktopPath && m.desktopPath.endsWith("/" + storageId)))) {
                return i;
            }
        }
        return -1;
    }

    function findAppItemMap(storageId: string) {
        if (!storageId) {
            return null;
        }
        const favIdx = findFavIndex(storageId);
        if (favIdx >= 0) {
            return Plasmoid.favsListModel.itemMap(favIdx);
        }
        for (let i = 0; i < 300; ++i) {
            const m = Plasmoid.applicationListModel.itemMap(i);
            if (!m || (!m.storageId && !m.name)) {
                break;
            }
            if (m.storageId === storageId || (m.desktopPath && m.desktopPath.endsWith("/" + storageId))) {
                return m;
            }
        }
        return null;
    }

    function forceStopApp(storageId: string) {
        if (!storageId) {
            return;
        }
        const baseId = storageId.endsWith(".desktop") ? storageId.slice(0, -8) : storageId;
        for (let i = 0; i < tasksModel.count; ++i) {
            const idx = tasksModel.makeModelIndex(i);
            const obj = runningApps.objectAt(i);
            const appId = obj ? (obj.appId ?? "") : "";
            if (appId === storageId || appId === baseId || appId.toLowerCase() === baseId.toLowerCase()) {
                tasksModel.requestClose(idx);
            }
        }
    }

    function requestOptions(storageId: string, name: string, iconName: string, description: string, mover: Item) {
        if (!storageId) {
            return;
        }
        let resolvedIcon = iconName;
        if (!resolvedIcon) {
            const m = findAppItemMap(storageId);
            if (m && m.icon) {
                resolvedIcon = m.icon;
            }
        }
        root.optionsRequested({
            storageId: storageId,
            name: name,
            iconName: resolvedIcon || "applications-multimedia",
            description: description,
            running: root.isRunning(storageId),
            canMove: mover !== null
        }, mover);
    }

    // Back goes to the first row before it opens the home overlay
    Bigscreen.BackHandler.enabled: root.scrolledDown
    Bigscreen.BackHandler.onActivated: {
        Bigscreen.NavigationRumble.playNavigationRumble();
        root.activateAppView();
    }

    function activateAppView() {
        if (root.activeCategory === "media" && mediaView.visible) {
            mediaView.forceActiveFocus();
        } else {
            favAppsView.currentViewDownwards?.forceActiveFocus();
        }
    }

    // Rows above the focused row fade out, rows below are dimmed
    function sectionOpacity(section: Item): real {
        const current = launcherHomeColumn.currentSection;
        if (!current || section === current) {
            return 1;
        }
        return section.y < current.y ? 0 : 0.55;
    }

    Component.onCompleted: {
        activateAppView();
        if (Plasmoid.favsListModel.count > 0) {
            const firstFav = Plasmoid.favsListModel.itemMap(0);
            if (firstFav && firstFav.name) {
                updateFocusedApp(firstFav.name, firstFav.comment || "", firstFav.icon || "", firstFav.storageId || "", i18n("FAVORITE"));
            }
        }
    }

    TaskManager.TasksModel {
        id: tasksModel
        filterByVirtualDesktop: false
        filterByActivity: false
        filterNotMaximized: false
        filterByScreen: false
        filterHidden: true
        groupMode: TaskManager.TasksModel.GroupDisabled
    }

    Instantiator {
        id: runningApps
        model: tasksModel
        delegate: QtObject {
            required property var model
            readonly property string appId: model.AppId ?? ""
        }
    }

    readonly property var runningAppIds: {
        const ids = [];
        for (let i = 0; i < runningApps.count; ++i) {
            const obj = runningApps.objectAt(i);
            if (obj && obj.appId.length > 0) {
                ids.push(obj.appId);
            }
        }
        return ids;
    }

    onRunningAppIdsChanged: {
        if (root.focusedApp && root.focusedApp.storageId) {
            root.focusedApp = {
                name: root.focusedApp.name,
                subtitle: root.focusedApp.subtitle,
                iconName: root.focusedApp.iconName,
                storageId: root.focusedApp.storageId,
                running: root.isRunning(root.focusedApp.storageId),
                category: root.focusedApp.category
            };
        }
    }

    function isRunning(storageId: string): bool {
        if (!storageId) {
            return false;
        }
        const appId = storageId.endsWith(".desktop") ? storageId.slice(0, -8) : storageId;
        return runningAppIds.includes(storageId) || runningAppIds.includes(appId);
    }

    Connections {
        target: Plasmoid.applicationListModel
        ignoreUnknownSignals: true

        function onBlocklistChanged() {
            recentModel.invalidateFilter();
            mediaModel.invalidateFilter();
        }
    }

    ColumnLayout {
        id: launcherHomeColumn
        anchors {
            left: parent.left
            right: parent.right
        }
        property Item currentSection
        readonly property Item firstSection: favAppsView.currentViewDownwards

        y: root.startY
        function intendedY() {
            if (!currentSection) {
                return startY;
            } else if (firstSection == currentSection) {
                return startY;
            }
            return Math.round(-currentSection.y + startY - currentSection.height / 2);
        }

        onCurrentSectionChanged: {
            // Use manual Animation instead of Behavior to prevent animations every time the screen is resized
            y = y; // Break binding before starting animation to prevent glitches
            yAnim.to = intendedY();
            yAnim.restart();
        }

        NumberAnimation on y {
            id: yAnim
            duration: Kirigami.Units.veryLongDuration
            easing.type: Easing.OutCubic

            // Set binding so that screen resizes affect Y
            onFinished: {
                launcherHomeColumn.y = Qt.binding(() => launcherHomeColumn.intendedY());
            }
        }

        spacing: Kirigami.Units.largeSpacing * 3

        DelegateListView {
            id: favAppsView
            // Recursively get the next visible view
            property var currentViewUpwards: visible ? favAppsView : root.navigationUp
            property var currentViewDownwards: visible ? favAppsView : mediaView.currentViewDownwards

            title: i18n("Favorites")
            opacity: root.sectionOpacity(favAppsView)
            Behavior on opacity { OpacityAnimator { duration: Kirigami.Units.longDuration } }
            model: Plasmoid.favsListModel
            visible: count > 0 && (root.activeCategory === "all" || root.activeCategory === "media")
            currentIndex: 0
            focus: visible
            onActiveFocusChanged: if (activeFocus)
                launcherHomeColumn.currentSection = favAppsView
            delegate: Delegates.FavDelegate {
                property var modelData: typeof model !== "undefined" ? model : null
                running: modelData ? root.isRunning(modelData.ApplicationStorageIdRole) : false
                onIsCurrentChanged: {
                    if (isCurrent && modelData) {
                        root.updateFocusedApp(text, subtitle, icon.name, modelData.ApplicationStorageIdRole, i18n("FAVORITE"));
                    }
                }
                onLongClick: root.requestOptions(modelData.ApplicationStorageIdRole, text, icon.name, subtitle, null)
            }

            navigationUp: root.navigationUp
            navigationDown: mediaView.currentViewDownwards
        }

        DelegateListView {
            id: mediaView
            property var currentViewUpwards: visible ? mediaView : favAppsView.currentViewUpwards
            property var currentViewDownwards: visible ? mediaView : recentView.currentViewDownwards

            title: i18n("Watch Now")
            opacity: root.sectionOpacity(mediaView)
            Behavior on opacity { OpacityAnimator { duration: Kirigami.Units.longDuration } }
            columnOffset: -0.5
            cardAspectRatio: 9 / 16
            visible: count > 0 && (root.activeCategory === "all" || root.activeCategory === "media")
            enabled: count > 0
            model: KItemModels.KSortFilterProxyModel {
                id: mediaModel
                sourceModel: Plasmoid.applicationListModel
                filterRoleName: "ApplicationCategoriesRole"
                filterRowCallback: function (source_row, source_parent) {
                    var cats = sourceModel.data(sourceModel.index(source_row, 0, source_parent), ApplicationListModel.ApplicationCategoriesRole);
                    if (!cats) {
                        return false;
                    }
                    return cats.indexOf("AudioVideo") !== -1 || cats.indexOf("Video") !== -1 || cats.indexOf("TV") !== -1;
                }
            }

            currentIndex: 0
            focus: visible && (favAppsView.currentViewUpwards === root.navigationUp)
            onActiveFocusChanged: if (activeFocus)
                launcherHomeColumn.currentSection = mediaView
            delegate: Delegates.AppDelegate {
                property var modelData: typeof model !== "undefined" ? model : null
                running: root.isRunning(applicationStorageId)
                onIsCurrentChanged: {
                    if (isCurrent) {
                        root.updateFocusedApp(text, subtitle, icon.name, applicationStorageId, i18n("WATCH NOW"));
                    }
                }
                onLongClick: root.requestOptions(applicationStorageId, text, icon.name, subtitle, null)
            }

            navigationUp: favAppsView.currentViewUpwards
            navigationDown: recentView.currentViewDownwards
        }

        DelegateListView {
            id: recentView
            property var currentViewUpwards: visible ? recentView : mediaView.currentViewUpwards
            property var currentViewDownwards: visible ? recentView : appsView.currentViewDownwards
            readonly property int favoriteIdRole: Qt.UserRole + 3

            function sourceIndex(row) {
                return recentView.model.mapToSource(recentView.model.index(row, 0));
            }

            title: i18n("Continue & Recent")
            opacity: root.sectionOpacity(recentView)
            Behavior on opacity { OpacityAnimator { duration: Kirigami.Units.longDuration } }
            model: KItemModels.KSortFilterProxyModel {
                id: recentModel
                sourceModel: Kicker.RecentUsageModel {
                    shownItems: Kicker.RecentUsageModel.OnlyApps
                }
                filterRowCallback: function(sourceRow, sourceParent) {
                    const sourceIndex = sourceModel.index(sourceRow, 0, sourceParent);
                    const storageId = sourceIndex.data(recentView.favoriteIdRole);
                    return !Plasmoid.applicationListModel.isApplicationBlocklisted(storageId);
                }
            }

            visible: Plasmoid.configuration.showRecent && count > 0 && root.activeCategory === "all"
            currentIndex: 0
            focus: visible && (mediaView.currentViewUpwards === root.navigationUp)
            onActiveFocusChanged: if (activeFocus)
                launcherHomeColumn.currentSection = recentView

            delegate: Delegates.AppDelegate {
                property real sectionOpacity: 1.0
                property var modelData: typeof model !== "undefined" ? model : null
                applicationStorageId: modelData ? (modelData.favoriteId ?? "") : ""
                launchApplication: function() {
                    recentView.model.sourceModel.trigger(recentView.sourceIndex(index).row, "", null);
                }
                iconImage: model.decoration
                text: model.display
                subtitle: model.description ?? ""
                running: root.isRunning(applicationStorageId)
                onIsCurrentChanged: {
                    if (isCurrent) {
                        root.updateFocusedApp(text, subtitle, icon.name, applicationStorageId, i18n("CONTINUE & RECENT"));
                    }
                }
                onLongClick: root.requestOptions(applicationStorageId, text, "", subtitle, null)
            }

            navigationUp: mediaView.currentViewUpwards
            navigationDown: appsView.currentViewDownwards
        }

        DelegateListView {
            id: appsView
            property var currentViewUpwards: visible ? appsView : recentView.currentViewUpwards
            property var currentViewDownwards: visible ? appsView : gamesView.currentViewDownwards

            title: i18n("Applications")
            opacity: root.sectionOpacity(appsView)
            Behavior on opacity { OpacityAnimator { duration: Kirigami.Units.longDuration } }
            visible: Plasmoid.configuration.showApplications && count > 0 && (root.activeCategory === "all" || root.activeCategory === "apps")
            enabled: count > 0
            model: KItemModels.KSortFilterProxyModel {
                sourceModel: Plasmoid.applicationListModel
                filterRoleName: "ApplicationCategoriesRole"
                filterRowCallback: function (source_row, source_parent) {
                    var cats = sourceModel.data(sourceModel.index(source_row, 0, source_parent), ApplicationListModel.ApplicationCategoriesRole);
                    if (!cats) {
                        return false;
                    }
                    return cats.indexOf("Game") === -1 || cats.indexOf("Application") !== -1;
                }
            }

            currentIndex: 0
            focus: visible && (recentView.currentViewUpwards === root.navigationUp)
            onActiveFocusChanged: if (activeFocus)
                launcherHomeColumn.currentSection = appsView
            delegate: Delegates.AppDelegate {
                property var modelData: typeof model !== "undefined" ? model : null
                running: root.isRunning(applicationStorageId)
                onIsCurrentChanged: {
                    if (isCurrent) {
                        root.updateFocusedApp(text, subtitle, icon.name, applicationStorageId, i18n("APPLICATION"));
                    }
                }
                onLongClick: root.requestOptions(applicationStorageId, text, icon.name, subtitle, null)
            }

            navigationUp: recentView.currentViewUpwards
            navigationDown: gamesView.currentViewDownwards
        }

        DelegateListView {
            id: gamesView
            property var currentViewUpwards: visible ? gamesView : appsView.currentViewUpwards
            property var currentViewDownwards: visible ? gamesView : null

            title: i18n("Games")
            opacity: root.sectionOpacity(gamesView)
            Behavior on opacity { OpacityAnimator { duration: Kirigami.Units.longDuration } }
            columnOffset: -1
            cardAspectRatio: 215 / 460 // Wider cards for games
            visible: Plasmoid.configuration.showGames && count > 0 && (root.activeCategory === "all" || root.activeCategory === "games")
            enabled: count > 0
            model: KItemModels.KSortFilterProxyModel {
                sourceModel: Plasmoid.applicationListModel
                filterRoleName: "ApplicationCategoriesRole"
                filterRowCallback: function (source_row, source_parent) {
                    return sourceModel.data(sourceModel.index(source_row, 0, source_parent), ApplicationListModel.ApplicationCategoriesRole).indexOf("Game") !== -1;
                }
            }

            currentIndex: 0
            focus: visible && (appsView.currentViewUpwards === root.navigationUp)
            onActiveFocusChanged: if (activeFocus)
                launcherHomeColumn.currentSection = gamesView
            delegate: Delegates.AppDelegate {
                property var modelData: typeof model !== "undefined" ? model : null
                running: root.isRunning(applicationStorageId)
                onIsCurrentChanged: {
                    if (isCurrent) {
                        root.updateFocusedApp(text, subtitle, icon.name, applicationStorageId, i18n("GAME"));
                    }
                }
                onLongClick: root.requestOptions(applicationStorageId, text, icon.name, subtitle, null)
            }

            navigationUp: appsView.currentViewUpwards
            navigationDown: null
        }
    }
}
