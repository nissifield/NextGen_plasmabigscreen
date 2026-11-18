/*
    SPDX-FileCopyrightText: 2019 Aditya Mehra <aix.m@outlook.com>
    SPDX-FileCopyrightText: 2019 Marco Martin <mart@kde.org>

    SPDX-License-Identifier: GPL-2.0-or-later
*/

import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import org.kde.bigscreen as Bigscreen
import org.kde.kirigami as Kirigami
import org.kde.plasma.plasmoid

IconDelegate {
    id: delegate
    useIconColors: Plasmoid.configuration.coloredTiles

    icon.name: modelData.ApplicationIconRole
    text: modelData ? modelData.ApplicationNameRole : ""
    subtitle: modelData ? (modelData.ApplicationCommentRole ?? "") : ""

    onClicked: {
        Bigscreen.NavigationSoundEffects.playClickedSound();
        Bigscreen.NavigationRumble.playConfirmRumble();
        const storageId = modelData ? (modelData.ApplicationStorageIdRole ?? "") : "";
        if (storageId === "return-to-desktop.desktop") {
            Plasmoid.applicationListModel.runApplication(storageId);
        } else if (storageId === "steam-bigpicture.desktop") {
            Plasmoid.showAppLaunchScreen(delegate.text, delegate.icon.name.length > 0 ? delegate.icon.name : model.decoration);
            Plasmoid.applicationListModel.runApplication(storageId);
        } else if (Plasmoid.applicationListModel.isApplicationRunning(storageId)) {
            Plasmoid.applicationListModel.maximizeApplication(storageId);
        } else {
            Plasmoid.showAppLaunchScreen(delegate.text, delegate.icon.name.length > 0 ? delegate.icon.name : model.decoration);
            Plasmoid.applicationListModel.runApplication(storageId);
        }
    }
}
