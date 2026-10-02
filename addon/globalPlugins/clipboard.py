import globalPluginHandler
import ui
import api
import wx
import gui
import keyboardHandler
import controlTypes
import textInfos
import tones
import os
import json

DATA_FILE = os.path.join(os.path.dirname(__file__), "clipboardHistoryData.json")


def getCurrentText():
    try:
        info = api.getReviewPosition().copy()
        info.expand(textInfos.UNIT_LINE)
        text = info.text.strip()
        if text:
            return text
    except Exception:
        pass
    try:
        obj = api.getNavigatorObject()
        if obj.name:
            return obj.name.strip()
    except Exception:
        pass
    return None


def collectListItems():
    obj = api.getNavigatorObject()
    if not obj:
        return []
    container = obj.parent if obj.parent else obj
    items = []
    child = container.firstChild
    while child:
        try:
            if child.name and child.name.strip():
                items.append(child.name.strip())
        except Exception:
            pass
        try:
            child = child.next
        except Exception:
            break
    return items


def pasteTextIntoFocus(text):
    focus = api.getFocusObject()
    try:
        role = focus.role
    except Exception:
        role = None
    if role == controlTypes.Role.EDITABLETEXT:
        try:
            keyboardHandler.KeyboardInputGesture.fromName("control+v").send()
        except Exception:
            ui.message("Edit field not found")
    else:
        ui.message("Edit field not found")


class GlobalPlugin(globalPluginHandler.GlobalPlugin):

    def __init__(self):
        super(GlobalPlugin, self).__init__()
        self.history = []
        self.favorites = []
        self.masterPassword = None
        self.passwordHint = None
        self.passwordEntries = []
        self.loadData()

    def loadData(self):
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.history = data.get("history", [])
                    self.favorites = data.get("favorites", [])
                    self.masterPassword = data.get("masterPassword", None)
                    self.passwordHint = data.get("passwordHint", None)
                    self.passwordEntries = data.get("passwordEntries", [])
            except Exception:
                self.history = []
                self.favorites = []
                self.masterPassword = None
                self.passwordHint = None
                self.passwordEntries = []

    def saveData(self):
        try:
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump({
                    "history": self.history,
                    "favorites": self.favorites,
                    "masterPassword": self.masterPassword,
                    "passwordHint": self.passwordHint,
                    "passwordEntries": self.passwordEntries
                }, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def script_copyCurrent(self, gesture):
        text = getCurrentText()
        if not text:
            ui.message("Nothing to copy here")
            return
        self.history.append(text)
        self.saveData()
        api.copyToClip(text)
        ui.message("Copied: " + text)

    def script_appendCurrent(self, gesture):
        text = getCurrentText()
        if not text:
            ui.message("Nothing to copy here")
            return
        if self.history:
            self.history[-1] = self.history[-1] + " " + text
        else:
            self.history.append(text)
        self.saveData()
        api.copyToClip(self.history[-1])
        ui.message("Appended: " + text)

    def script_openHistory(self, gesture):
        wx.CallAfter(self.openHistoryFlow)

    def openHistoryFlow(self):
        dlg = ClipboardHistoryDialog(gui.mainFrame, self)
        gui.mainFrame.prePopup()
        dlg.Show()
        gui.mainFrame.postPopup()

    def script_copyList(self, gesture):
        tones.beep(400, 100)
        items = collectListItems()
        if not items:
            ui.message("No list found here")
            return
        tones.beep(800, 150)
        wx.CallAfter(self.openListCopyResult, items)

    def openListCopyResult(self, items):
        dlg = ListCopyResultDialog(gui.mainFrame, self, items)
        gui.mainFrame.prePopup()
        dlg.Show()
        gui.mainFrame.postPopup()

    def script_openFavorites(self, gesture):
        wx.CallAfter(self.openFavoritesFlow)

    def openFavoritesFlow(self):
        dlg = FavoritesDialog(gui.mainFrame, self)
        gui.mainFrame.prePopup()
        dlg.Show()
        gui.mainFrame.postPopup()

    def openPasswordManagerFlow(self):
        if not self.masterPassword:
            setupDlg = PasswordSetupDialog(gui.mainFrame)
            gui.mainFrame.prePopup()
            result = setupDlg.ShowModal()
            gui.mainFrame.postPopup()
            if result != wx.ID_OK:
                setupDlg.Destroy()
                return
            password, hint = setupDlg.getValues()
            setupDlg.Destroy()

            self.masterPassword = password
            self.passwordHint = hint
            self.saveData()

            promptDlg = SavePasswordPromptDialog(gui.mainFrame)
            gui.mainFrame.prePopup()
            promptResult = promptDlg.ShowModal()
            gui.mainFrame.postPopup()
            promptDlg.Destroy()

            if promptResult == wx.ID_SAVE:
                with wx.FileDialog(
                    gui.mainFrame,
                    "Save password backup as",
                    wildcard="Text files (*.txt)|*.txt",
                    style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT
                ) as fileDialog:
                    if fileDialog.ShowModal() != wx.ID_CANCEL:
                        path = fileDialog.GetPath()
                        try:
                            with open(path, "w", encoding="utf-8") as f:
                                f.write("Password: " + password + "\n")
                                f.write("Hint: " + hint + "\n")
                            ui.message("Backup saved")
                        except Exception:
                            ui.message("Could not save backup")

            dlg = PasswordManagerDialog(gui.mainFrame, self)
            gui.mainFrame.prePopup()
            dlg.Show()
            gui.mainFrame.postPopup()
        else:
            loginDlg = PasswordLoginDialog(gui.mainFrame, self)
            gui.mainFrame.prePopup()
            result = loginDlg.ShowModal()
            gui.mainFrame.postPopup()
            loginDlg.Destroy()
            if result != wx.ID_OK:
                return
            dlg = PasswordManagerDialog(gui.mainFrame, self)
            gui.mainFrame.prePopup()
            dlg.Show()
            gui.mainFrame.postPopup()

    def script_openPasswordManager(self, gesture):
        wx.CallAfter(self.openPasswordManagerFlow)

    __gestures = {
        "kb:NVDA+shift+c": "copyCurrent",
        "kb:NVDA+shift+a": "appendCurrent",
        "kb:NVDA+shift+v": "openHistory",
        "kb:NVDA+shift+l": "copyList",
        "kb:NVDA+shift+f": "openFavorites",
        "kb:NVDA+shift+k": "openPasswordManager",
    }


class ListCopyResultDialog(wx.Dialog):
    def __init__(self, parent, plugin, items):
        super(ListCopyResultDialog, self).__init__(parent, title="List Copy Complete", size=(400, 200))
        self.plugin = plugin
        self.items = items

        mainSizer = wx.BoxSizer(wx.VERTICAL)

        infoLabel = wx.StaticText(self, label=str(len(items)) + " item(s) found. What would you like to do?")
        mainSizer.Add(infoLabel, 0, wx.ALL, 15)

        buttonSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.copyButton = wx.Button(self, label="Copy")
        self.saveButton = wx.Button(self, label="Save")
        self.closeButton = wx.Button(self, label="Close")
        buttonSizer.Add(self.copyButton, 0, wx.ALL, 5)
        buttonSizer.Add(self.saveButton, 0, wx.ALL, 5)
        buttonSizer.Add(self.closeButton, 0, wx.ALL, 5)
        mainSizer.Add(buttonSizer, 0, wx.ALIGN_CENTER)

        self.SetSizer(mainSizer)
        self.Layout()

        self.copyButton.Bind(wx.EVT_BUTTON, self.onCopy)
        self.saveButton.Bind(wx.EVT_BUTTON, self.onSave)
        self.closeButton.Bind(wx.EVT_BUTTON, self.onClose)

        self.copyButton.SetFocus()

    def onCopy(self, event):
        combined = self.items[0]
        for item in self.items[1:]:
            combined = combined + " " + item
        self.plugin.history.append(combined)
        self.plugin.saveData()
        joined = "\n".join(self.items)
        api.copyToClip(joined)
        ui.message("Copied " + str(len(self.items)) + " items")
        self.Close()

    def onSave(self, event):
        with wx.FileDialog(
            self,
            "Save list as",
            wildcard="Text files (*.txt)|*.txt",
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT
        ) as fileDialog:
            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return
            path = fileDialog.GetPath()
            try:
                with open(path, "w", encoding="utf-8") as f:
                    for item in self.items:
                        f.write(item + "\n")
                ui.message("List saved")
            except Exception:
                ui.message("Could not save file")
        self.Close()

    def onClose(self, event):
        self.Close()


class AddFavoriteDialog(wx.Dialog):
    def __init__(self, parent, title="Add Favorite"):
        super(AddFavoriteDialog, self).__init__(parent, title=title, size=(400, 200))

        mainSizer = wx.BoxSizer(wx.VERTICAL)

        label = wx.StaticText(self, label="Enter your text:")
        mainSizer.Add(label, 0, wx.ALL, 10)

        self.textBox = wx.TextCtrl(self, style=wx.TE_MULTILINE)
        mainSizer.Add(self.textBox, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

        buttonSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.okButton = wx.Button(self, label="OK")
        self.cancelButton = wx.Button(self, label="Cancel")
        buttonSizer.Add(self.okButton, 0, wx.ALL, 5)
        buttonSizer.Add(self.cancelButton, 0, wx.ALL, 5)
        mainSizer.Add(buttonSizer, 0, wx.ALIGN_CENTER | wx.ALL, 5)

        self.SetSizer(mainSizer)
        self.Layout()

        self.okButton.Bind(wx.EVT_BUTTON, self.onOk)
        self.cancelButton.Bind(wx.EVT_BUTTON, self.onCancel)

        self.textBox.SetFocus()

    def onOk(self, event):
        self.EndModal(wx.ID_OK)

    def onCancel(self, event):
        self.EndModal(wx.ID_CANCEL)

    def getText(self):
        return self.textBox.GetValue().strip()


class FavoritesManageDialog(wx.Dialog):
    def __init__(self, parent, plugin):
        super(FavoritesManageDialog, self).__init__(parent, title="Manage Favorites", size=(450, 400))
        self.plugin = plugin

        mainSizer = wx.BoxSizer(wx.VERTICAL)

        self.checkList = wx.CheckListBox(self, choices=self.plugin.favorites)
        mainSizer.Add(self.checkList, 1, wx.EXPAND | wx.ALL, 10)

        topButtonSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.selectAllButton = wx.Button(self, label="Select All")
        topButtonSizer.Add(self.selectAllButton, 0, wx.ALL, 5)
        mainSizer.Add(topButtonSizer, 0, wx.ALIGN_LEFT | wx.ALL, 5)

        actionButtonSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.removeButton = wx.Button(self, label="Remove from Favorites")
        self.deleteButton = wx.Button(self, label="Delete")
        actionButtonSizer.Add(self.removeButton, 0, wx.ALL, 5)
        actionButtonSizer.Add(self.deleteButton, 0, wx.ALL, 5)
        mainSizer.Add(actionButtonSizer, 0, wx.ALIGN_LEFT | wx.ALL, 5)

        self.closeButton = wx.Button(self, label="Close")
        mainSizer.Add(self.closeButton, 0, wx.ALIGN_RIGHT | wx.ALL, 5)

        self.SetSizer(mainSizer)
        self.Layout()

        self.removeButton.Hide()
        self.deleteButton.Hide()
        self.Layout()

        self.checkList.Bind(wx.EVT_CHECKLISTBOX, self.onCheckChanged)
        self.checkList.Bind(wx.EVT_KEY_DOWN, self.onCheckListKeyDown)
        self.selectAllButton.Bind(wx.EVT_BUTTON, self.onSelectAll)
        self.removeButton.Bind(wx.EVT_BUTTON, self.onRemove)
        self.deleteButton.Bind(wx.EVT_BUTTON, self.onDelete)
        self.closeButton.Bind(wx.EVT_BUTTON, self.onClose)

        wx.CallAfter(self.checkList.SetFocus)

    def onCheckListKeyDown(self, event):
        keycode = event.GetKeyCode()
        if keycode == wx.WXK_SPACE:
            index = self.checkList.GetSelection()
            if index != wx.NOT_FOUND:
                newState = not self.checkList.IsChecked(index)
                self.checkList.Check(index, newState)
                self.updateActionButtons()
                ui.message("Checked" if newState else "Not checked")
        else:
            event.Skip()

    def getCheckedIndices(self):
        return [i for i in range(self.checkList.GetCount()) if self.checkList.IsChecked(i)]

    def updateActionButtons(self):
        anyChecked = len(self.getCheckedIndices()) > 0
        self.removeButton.Show(anyChecked)
        self.deleteButton.Show(anyChecked)
        self.Layout()

    def onCheckChanged(self, event):
        self.updateActionButtons()

    def onSelectAll(self, event):
        for i in range(self.checkList.GetCount()):
            self.checkList.Check(i, True)
        self.updateActionButtons()
        ui.message("All items selected")

    def onRemove(self, event):
        indices = self.getCheckedIndices()
        if not indices:
            ui.message("No items selected")
            return
        for i in sorted(indices, reverse=True):
            text = self.plugin.favorites[i]
            self.plugin.history.append(text)
            del self.plugin.favorites[i]
        self.checkList.Set(self.plugin.favorites)
        self.removeButton.Hide()
        self.deleteButton.Hide()
        self.Layout()
        ui.message("Moved " + str(len(indices)) + " item(s) to clipboard history")

    def onDelete(self, event):
        indices = self.getCheckedIndices()
        if not indices:
            ui.message("No items selected")
            return
        for i in sorted(indices, reverse=True):
            del self.plugin.favorites[i]
        self.checkList.Set(self.plugin.favorites)
        self.removeButton.Hide()
        self.deleteButton.Hide()
        self.Layout()
        ui.message("Deleted " + str(len(indices)) + " item(s)")

    def onClose(self, event):
        self.Close()


class FavoritesDialog(wx.Dialog):
    def __init__(self, parent, plugin):
        super(FavoritesDialog, self).__init__(parent, title="Favorites", size=(420, 400))
        self.plugin = plugin
        self.filteredIndices = list(range(len(self.plugin.favorites)))

        mainSizer = wx.BoxSizer(wx.VERTICAL)

        searchLabel = wx.StaticText(self, label="Search:")
        mainSizer.Add(searchLabel, 0, wx.LEFT | wx.TOP, 10)
        self.searchBox = wx.TextCtrl(self)
        mainSizer.Add(self.searchBox, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 10)

        self.listBox = wx.ListBox(self, choices=self.plugin.favorites, style=wx.LB_SINGLE)
        mainSizer.Add(self.listBox, 1, wx.EXPAND | wx.ALL, 10)

        buttonSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.newButton = wx.Button(self, label="New")
        self.manageButton = wx.Button(self, label="Manage")
        self.closeButton = wx.Button(self, label="Close")
        buttonSizer.Add(self.newButton, 0, wx.ALL, 5)
        buttonSizer.Add(self.manageButton, 0, wx.ALL, 5)
        buttonSizer.Add(self.closeButton, 0, wx.ALL, 5)
        mainSizer.Add(buttonSizer, 0, wx.ALIGN_CENTER | wx.ALL, 5)

        self.SetSizer(mainSizer)
        self.Layout()

        self.Bind(wx.EVT_CHAR_HOOK, self.onCharHook)
        self.searchBox.Bind(wx.EVT_TEXT, self.onSearchTextChanged)
        self.newButton.Bind(wx.EVT_BUTTON, self.onNew)
        self.manageButton.Bind(wx.EVT_BUTTON, self.onManage)
        self.closeButton.Bind(wx.EVT_BUTTON, self.onClose)

        self.searchBox.SetFocus()
        if self.plugin.favorites:
            self.listBox.SetSelection(len(self.plugin.favorites) - 1)

    def onSearchTextChanged(self, event):
        query = self.searchBox.GetValue().strip().lower()
        if not query:
            self.filteredIndices = list(range(len(self.plugin.favorites)))
        else:
            self.filteredIndices = [
                i for i, text in enumerate(self.plugin.favorites)
                if query in text.lower()
            ]
        displayItems = [self.plugin.favorites[i] for i in self.filteredIndices]
        self.listBox.Set(displayItems)
        if displayItems:
            self.listBox.SetSelection(0)

    def onCharHook(self, event):
        keycode = event.GetKeyCode()
        focused = self.FindFocus()
        if keycode in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER) and focused in (self.listBox, self.searchBox):
            self.pasteSelected()
        elif keycode == wx.WXK_ESCAPE:
            self.Close()
        else:
            event.Skip()

    def getSelectedRealIndex(self):
        displayIndex = self.listBox.GetSelection()
        if displayIndex == wx.NOT_FOUND or displayIndex >= len(self.filteredIndices):
            return None
        return self.filteredIndices[displayIndex]

    def pasteSelected(self):
        realIndex = self.getSelectedRealIndex()
        if realIndex is None:
            ui.message("No item selected")
            return
        text = self.plugin.favorites[realIndex]
        api.copyToClip(text)
        self.Close()
        wx.CallLater(500, pasteTextIntoFocus, text)

    def onNew(self, event):
        dlg = AddFavoriteDialog(self)
        result = dlg.ShowModal()
        if result == wx.ID_OK:
            text = dlg.getText()
            if text:
                self.plugin.favorites.append(text)
                self.plugin.saveData()
                self.filteredIndices = list(range(len(self.plugin.favorites)))
                self.listBox.Set(self.plugin.favorites)
                self.listBox.SetSelection(len(self.plugin.favorites) - 1)
                ui.message("Favorite added")
            else:
                ui.message("No text entered")
        dlg.Destroy()

    def onManage(self, event):
        dlg = FavoritesManageDialog(self, self.plugin)
        dlg.ShowModal()
        self.plugin.saveData()
        self.filteredIndices = list(range(len(self.plugin.favorites)))
        self.listBox.Set(self.plugin.favorites)

    def onClose(self, event):
        self.Close()


class PasswordSetupDialog(wx.Dialog):
    def __init__(self, parent):
        super(PasswordSetupDialog, self).__init__(parent, title="Set Up Password Manager", size=(400, 270))

        mainSizer = wx.BoxSizer(wx.VERTICAL)

        passLabel = wx.StaticText(self, label="Enter your password:")
        mainSizer.Add(passLabel, 0, wx.LEFT | wx.TOP, 10)

        self.passwordBox = wx.TextCtrl(self, style=wx.TE_PASSWORD)
        mainSizer.Add(self.passwordBox, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 10)

        self.showPassCheck = wx.CheckBox(self, label="Show Password")
        mainSizer.Add(self.showPassCheck, 0, wx.LEFT | wx.TOP, 10)

        hintLabel = wx.StaticText(self, label="Enter a hint for this password:")
        mainSizer.Add(hintLabel, 0, wx.LEFT | wx.TOP, 10)
        self.hintBox = wx.TextCtrl(self)
        mainSizer.Add(self.hintBox, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 10)

        buttonSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.okButton = wx.Button(self, label="OK")
        self.cancelButton = wx.Button(self, label="Cancel")
        buttonSizer.Add(self.okButton, 0, wx.ALL, 5)
        buttonSizer.Add(self.cancelButton, 0, wx.ALL, 5)
        mainSizer.Add(buttonSizer, 0, wx.ALIGN_CENTER | wx.ALL, 10)

        self.SetSizer(mainSizer)
        self.Layout()

        self.okButton.Bind(wx.EVT_BUTTON, self.onOk)
        self.cancelButton.Bind(wx.EVT_BUTTON, self.onCancel)
        self.showPassCheck.Bind(wx.EVT_CHECKBOX, self.onToggleShowPassword)
        self.passwordBox.Bind(wx.EVT_CHAR_HOOK, self.onTextCharHook)
        self.hintBox.Bind(wx.EVT_CHAR_HOOK, self.onTextCharHook)

        self.passwordBox.SetFocus()

    def onOk(self, event):
        password = self.passwordBox.GetValue().strip()
        hint = self.hintBox.GetValue().strip()
        if not password or not hint:
            ui.message("Please fill in both fields")
            return
        self.EndModal(wx.ID_OK)

    def onCancel(self, event):
        self.EndModal(wx.ID_CANCEL)

    def onToggleShowPassword(self, event):
        currentText = self.passwordBox.GetValue()
        cursorPos = self.passwordBox.GetInsertionPoint()
        isShown = self.showPassCheck.GetValue()
        
        self.passwordBox.Destroy()
        if isShown:
            self.passwordBox = wx.TextCtrl(self, value=currentText)
        else:
            self.passwordBox = wx.TextCtrl(self, value=currentText, style=wx.TE_PASSWORD)
            
        self.passwordBox.Bind(wx.EVT_CHAR_HOOK, self.onTextCharHook)
        
        mainSizer = self.GetSizer()
        mainSizer.Insert(1, self.passwordBox, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 10)
        self.Layout()
        
        self.passwordBox.SetInsertionPoint(min(cursorPos, len(currentText)))
        self.passwordBox.SetFocus()

    def onTextCharHook(self, event):
        keycode = event.GetKeyCode()
        if keycode in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self.onOk(event)
        else:
            event.Skip()

    def getValues(self):
        return self.passwordBox.GetValue().strip(), self.hintBox.GetValue().strip()


class SavePasswordPromptDialog(wx.Dialog):
    def __init__(self, parent):
        super(SavePasswordPromptDialog, self).__init__(parent, title="Save Password", size=(400, 150))

        mainSizer = wx.BoxSizer(wx.VERTICAL)

        label = wx.StaticText(self, label="Do you want to save your password as a backup file?")
        mainSizer.Add(label, 0, wx.ALL, 15)

        buttonSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.saveButton = wx.Button(self, label="Save")
        self.cancelButton = wx.Button(self, label="Cancel")
        buttonSizer.Add(self.saveButton, 0, wx.ALL, 5)
        buttonSizer.Add(self.cancelButton, 0, wx.ALL, 5)
        mainSizer.Add(buttonSizer, 0, wx.ALIGN_CENTER)

        self.SetSizer(mainSizer)
        self.Layout()

        self.saveButton.Bind(wx.EVT_BUTTON, self.onSave)
        self.cancelButton.Bind(wx.EVT_BUTTON, self.onCancel)

        self.saveButton.SetFocus()

    def onSave(self, event):
        self.EndModal(wx.ID_SAVE)

    def onCancel(self, event):
        self.EndModal(wx.ID_CANCEL)


class PasswordForgotDialog(wx.Dialog):
    def __init__(self, parent, plugin):
        super(PasswordForgotDialog, self).__init__(parent, title="Reset Password via Hint", size=(400, 220))
        self.plugin = plugin

        mainSizer = wx.BoxSizer(wx.VERTICAL)

        label = wx.StaticText(self, label="Enter your password hint:")
        mainSizer.Add(label, 0, wx.LEFT | wx.TOP, 10)
        self.hintBox = wx.TextCtrl(self)
        mainSizer.Add(self.hintBox, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 10)

        buttonSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.okButton = wx.Button(self, label="OK")
        self.cancelButton = wx.Button(self, label="Cancel")
        buttonSizer.Add(self.okButton, 0, wx.ALL, 5)
        buttonSizer.Add(self.cancelButton, 0, wx.ALL, 5)
        mainSizer.Add(buttonSizer, 0, wx.ALIGN_CENTER | wx.ALL, 10)

        self.SetSizer(mainSizer)
        self.Layout()

        self.okButton.Bind(wx.EVT_BUTTON, self.onOk)
        self.cancelButton.Bind(wx.EVT_BUTTON, self.onCancel)
        self.hintBox.Bind(wx.EVT_CHAR_HOOK, self.onTextCharHook)

        self.hintBox.SetFocus()

    def onOk(self, event):
        enteredHint = self.hintBox.GetValue().strip().lower()
        savedHint = self.plugin.passwordHint.strip().lower() if self.plugin.passwordHint else ""
        if enteredHint and enteredHint == savedHint:
            self.EndModal(wx.ID_OK)
        else:
            ui.message("Incorrect hint")
            self.hintBox.SetValue("")
            self.hintBox.SetFocus()

    def onCancel(self, event):
        self.EndModal(wx.ID_CANCEL)

    def onTextCharHook(self, event):
        keycode = event.GetKeyCode()
        if keycode in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self.onOk(event)
        else:
            event.Skip()


class PasswordResetDialog(wx.Dialog):
    def __init__(self, parent):
        super(PasswordResetDialog, self).__init__(parent, title="Create New Password", size=(400, 230))

        mainSizer = wx.BoxSizer(wx.VERTICAL)

        label = wx.StaticText(self, label="Enter your new password:")
        mainSizer.Add(label, 0, wx.LEFT | wx.TOP, 10)

        self.passwordBox = wx.TextCtrl(self, style=wx.TE_PASSWORD)
        mainSizer.Add(self.passwordBox, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 10)

        self.showPassCheck = wx.CheckBox(self, label="Show Password")
        mainSizer.Add(self.showPassCheck, 0, wx.LEFT | wx.TOP, 10)

        buttonSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.okButton = wx.Button(self, label="OK")
        self.cancelButton = wx.Button(self, label="Cancel")
        buttonSizer.Add(self.okButton, 0, wx.ALL, 5)
        buttonSizer.Add(self.cancelButton, 0, wx.ALL, 5)
        mainSizer.Add(buttonSizer, 0, wx.ALIGN_CENTER | wx.ALL, 10)

        self.SetSizer(mainSizer)
        self.Layout()

        self.okButton.Bind(wx.EVT_BUTTON, self.onOk)
        self.cancelButton.Bind(wx.EVT_BUTTON, self.onCancel)
        self.showPassCheck.Bind(wx.EVT_CHECKBOX, self.onToggleShowPassword)
        self.passwordBox.Bind(wx.EVT_CHAR_HOOK, self.onTextCharHook)

        self.passwordBox.SetFocus()

    def onOk(self, event):
        password = self.passwordBox.GetValue().strip()
        if not password:
            ui.message("Please enter a new password")
            return
        self.EndModal(wx.ID_OK)

    def onCancel(self, event):
        self.EndModal(wx.ID_CANCEL)

    def onToggleShowPassword(self, event):
        currentText = self.passwordBox.GetValue()
        cursorPos = self.passwordBox.GetInsertionPoint()
        isShown = self.showPassCheck.GetValue()
        
        self.passwordBox.Destroy()
        if isShown:
            self.passwordBox = wx.TextCtrl(self, value=currentText)
        else:
            self.passwordBox = wx.TextCtrl(self, value=currentText, style=wx.TE_PASSWORD)
            
        self.passwordBox.Bind(wx.EVT_CHAR_HOOK, self.onTextCharHook)
        
        mainSizer = self.GetSizer()
        mainSizer.Insert(1, self.passwordBox, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 10)
        self.Layout()
        
        self.passwordBox.SetInsertionPoint(min(cursorPos, len(currentText)))
        self.passwordBox.SetFocus()

    def onTextCharHook(self, event):
        keycode = event.GetKeyCode()
        if keycode in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self.onOk(event)
        else:
            event.Skip()

    def getPassword(self):
        return self.passwordBox.GetValue().strip()


class PasswordVerifyDialog(wx.Dialog):
    def __init__(self, parent, plugin):
        super(PasswordVerifyDialog, self).__init__(parent, title="Verify Current Password", size=(400, 230))
        self.plugin = plugin

        mainSizer = wx.BoxSizer(wx.VERTICAL)

        label = wx.StaticText(self, label="Enter your current password:")
        mainSizer.Add(label, 0, wx.LEFT | wx.TOP, 10)

        self.passwordBox = wx.TextCtrl(self, style=wx.TE_PASSWORD)
        mainSizer.Add(self.passwordBox, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 10)

        self.showPassCheck = wx.CheckBox(self, label="Show Password")
        mainSizer.Add(self.showPassCheck, 0, wx.LEFT | wx.TOP, 10)

        buttonSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.okButton = wx.Button(self, label="OK")
        self.cancelButton = wx.Button(self, label="Cancel")
        buttonSizer.Add(self.okButton, 0, wx.ALL, 5)
        buttonSizer.Add(self.cancelButton, 0, wx.ALL, 5)
        mainSizer.Add(buttonSizer, 0, wx.ALIGN_CENTER | wx.ALL, 10)

        self.SetSizer(mainSizer)
        self.Layout()

        self.okButton.Bind(wx.EVT_BUTTON, self.onOk)
        self.cancelButton.Bind(wx.EVT_BUTTON, self.onCancel)
        self.showPassCheck.Bind(wx.EVT_CHECKBOX, self.onToggleShowPassword)
        self.passwordBox.Bind(wx.EVT_CHAR_HOOK, self.onTextCharHook)

        self.passwordBox.SetFocus()

    def onOk(self, event):
        entered = self.passwordBox.GetValue().strip()
        if entered == self.plugin.masterPassword:
            self.EndModal(wx.ID_OK)
        else:
            ui.message("Incorrect password")
            self.passwordBox.SetValue("")
            self.passwordBox.SetFocus()

    def onCancel(self, event):
        self.EndModal(wx.ID_CANCEL)

    def onToggleShowPassword(self, event):
        currentText = self.passwordBox.GetValue()
        cursorPos = self.passwordBox.GetInsertionPoint()
        isShown = self.showPassCheck.GetValue()
        
        self.passwordBox.Destroy()
        if isShown:
            self.passwordBox = wx.TextCtrl(self, value=currentText)
        else:
            self.passwordBox = wx.TextCtrl(self, value=currentText, style=wx.TE_PASSWORD)
            
        self.passwordBox.Bind(wx.EVT_CHAR_HOOK, self.onTextCharHook)
        
        mainSizer = self.GetSizer()
        mainSizer.Insert(1, self.passwordBox, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 10)
        self.Layout()
        
        self.passwordBox.SetInsertionPoint(min(cursorPos, len(currentText)))
        self.passwordBox.SetFocus()

    def onTextCharHook(self, event):
        keycode = event.GetKeyCode()
        if keycode in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self.onOk(event)
        else:
            event.Skip()


class PasswordChangeDialog(wx.Dialog):
    def __init__(self, parent, plugin):
        super(PasswordChangeDialog, self).__init__(parent, title="Change Password & Hint", size=(400, 270))
        self.plugin = plugin

        mainSizer = wx.BoxSizer(wx.VERTICAL)

        passLabel = wx.StaticText(self, label="Enter new password:")
        mainSizer.Add(passLabel, 0, wx.LEFT | wx.TOP, 10)

        self.passwordBox = wx.TextCtrl(self, style=wx.TE_PASSWORD)
        mainSizer.Add(self.passwordBox, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 10)

        self.showPassCheck = wx.CheckBox(self, label="Show Password")
        mainSizer.Add(self.showPassCheck, 0, wx.LEFT | wx.TOP, 10)

        hintLabel = wx.StaticText(self, label="Enter new hint:")
        mainSizer.Add(hintLabel, 0, wx.LEFT | wx.TOP, 10)
        self.hintBox = wx.TextCtrl(self)
        if self.plugin.passwordHint:
            self.hintBox.SetValue(self.plugin.passwordHint)
        mainSizer.Add(self.hintBox, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 10)

        buttonSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.okButton = wx.Button(self, label="OK")
        self.cancelButton = wx.Button(self, label="Cancel")
        buttonSizer.Add(self.okButton, 0, wx.ALL, 5)
        buttonSizer.Add(self.cancelButton, 0, wx.ALL, 5)
        mainSizer.Add(buttonSizer, 0, wx.ALIGN_CENTER | wx.ALL, 10)

        self.SetSizer(mainSizer)
        self.Layout()

        self.okButton.Bind(wx.EVT_BUTTON, self.onOk)
        self.cancelButton.Bind(wx.EVT_BUTTON, self.onCancel)
        self.showPassCheck.Bind(wx.EVT_CHECKBOX, self.onToggleShowPassword)
        self.passwordBox.Bind(wx.EVT_CHAR_HOOK, self.onTextCharHook)
        self.hintBox.Bind(wx.EVT_CHAR_HOOK, self.onTextCharHook)

        self.passwordBox.SetFocus()

    def onOk(self, event):
        password = self.passwordBox.GetValue().strip()
        hint = self.hintBox.GetValue().strip()
        if not password or not hint:
            ui.message("Please fill in both fields")
            return
        self.EndModal(wx.ID_OK)

    def onCancel(self, event):
        self.EndModal(wx.ID_CANCEL)

    def onToggleShowPassword(self, event):
        currentText = self.passwordBox.GetValue()
        cursorPos = self.passwordBox.GetInsertionPoint()
        isShown = self.showPassCheck.GetValue()
        
        self.passwordBox.Destroy()
        if isShown:
            self.passwordBox = wx.TextCtrl(self, value=currentText)
        else:
            self.passwordBox = wx.TextCtrl(self, value=currentText, style=wx.TE_PASSWORD)
            
        self.passwordBox.Bind(wx.EVT_CHAR_HOOK, self.onTextCharHook)
        
        mainSizer = self.GetSizer()
        mainSizer.Insert(1, self.passwordBox, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 10)
        self.Layout()
        
        self.passwordBox.SetInsertionPoint(min(cursorPos, len(currentText)))
        self.passwordBox.SetFocus()

    def onTextCharHook(self, event):
        keycode = event.GetKeyCode()
        if keycode in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self.onOk(event)
        else:
            event.Skip()

    def getValues(self):
        return self.passwordBox.GetValue().strip(), self.hintBox.GetValue().strip()


class PasswordLoginDialog(wx.Dialog):
    def __init__(self, parent, plugin):
        super(PasswordLoginDialog, self).__init__(parent, title="Enter Password", size=(400, 230))
        self.plugin = plugin

        mainSizer = wx.BoxSizer(wx.VERTICAL)

        label = wx.StaticText(self, label="Enter your password:")
        mainSizer.Add(label, 0, wx.LEFT | wx.TOP, 10)

        self.passwordBox = wx.TextCtrl(self, style=wx.TE_PASSWORD)
        mainSizer.Add(self.passwordBox, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 10)

        self.showPassCheck = wx.CheckBox(self, label="Show Password")
        mainSizer.Add(self.showPassCheck, 0, wx.LEFT | wx.TOP, 10)

        buttonSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.okButton = wx.Button(self, label="OK")
        self.forgotButton = wx.Button(self, label="Forgot Password")
        self.cancelButton = wx.Button(self, label="Cancel")
        buttonSizer.Add(self.okButton, 0, wx.ALL, 5)
        buttonSizer.Add(self.forgotButton, 0, wx.ALL, 5)
        buttonSizer.Add(self.cancelButton, 0, wx.ALL, 5)
        mainSizer.Add(buttonSizer, 0, wx.ALIGN_CENTER | wx.ALL, 10)

        self.SetSizer(mainSizer)
        self.Layout()

        self.okButton.Bind(wx.EVT_BUTTON, self.onOk)
        self.forgotButton.Bind(wx.EVT_BUTTON, self.onForgot)
        self.cancelButton.Bind(wx.EVT_BUTTON, self.onCancel)
        self.showPassCheck.Bind(wx.EVT_CHECKBOX, self.onToggleShowPassword)
        self.passwordBox.Bind(wx.EVT_CHAR_HOOK, self.onTextCharHook)

        self.passwordBox.SetFocus()

    def onOk(self, event):
        entered = self.passwordBox.GetValue().strip()
        if entered == self.plugin.masterPassword:
            self.EndModal(wx.ID_OK)
        else:
            ui.message("Incorrect password")
            self.passwordBox.SetValue("")
            self.passwordBox.SetFocus()

    def onToggleShowPassword(self, event):
        currentText = self.passwordBox.GetValue()
        cursorPos = self.passwordBox.GetInsertionPoint()
        isShown = self.showPassCheck.GetValue()
        
        self.passwordBox.Destroy()
        if isShown:
            self.passwordBox = wx.TextCtrl(self, value=currentText)
        else:
            self.passwordBox = wx.TextCtrl(self, value=currentText, style=wx.TE_PASSWORD)
            
        self.passwordBox.Bind(wx.EVT_CHAR_HOOK, self.onTextCharHook)
        
        mainSizer = self.GetSizer()
        mainSizer.Insert(1, self.passwordBox, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 10)
        self.Layout()
        
        self.passwordBox.SetInsertionPoint(min(cursorPos, len(currentText)))
        self.passwordBox.SetFocus()

    def onTextCharHook(self, event):
        keycode = event.GetKeyCode()
        if keycode in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self.onOk(event)
        else:
            event.Skip()

    def onForgot(self, event):
        forgotDlg = PasswordForgotDialog(self, self.plugin)
        gui.mainFrame.prePopup()
        result = forgotDlg.ShowModal()
        gui.mainFrame.postPopup()
        forgotDlg.Destroy()

        if result == wx.ID_OK:
            resetDlg = PasswordResetDialog(self)
            gui.mainFrame.prePopup()
            resetResult = resetDlg.ShowModal()
            gui.mainFrame.postPopup()
            if resetResult == wx.ID_OK:
                newPass = resetDlg.getPassword()
                resetDlg.Destroy()
                self.plugin.masterPassword = newPass
                self.plugin.saveData()
                ui.message("Password reset successfully")
                self.EndModal(wx.ID_OK)
            else:
                resetDlg.Destroy()

    def onCancel(self, event):
        self.EndModal(wx.ID_CANCEL)


class PasswordManageDialog(wx.Dialog):
    def __init__(self, parent, plugin):
        super(PasswordManageDialog, self).__init__(parent, title="Manage Passwords", size=(450, 400))
        self.plugin = plugin

        mainSizer = wx.BoxSizer(wx.VERTICAL)

        self.checkList = wx.CheckListBox(self, choices=self.plugin.passwordEntries)
        mainSizer.Add(self.checkList, 1, wx.EXPAND | wx.ALL, 10)

        topButtonSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.selectAllButton = wx.Button(self, label="Select All")
        topButtonSizer.Add(self.selectAllButton, 0, wx.ALL, 5)
        mainSizer.Add(topButtonSizer, 0, wx.ALIGN_LEFT | wx.ALL, 5)

        actionButtonSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.deleteButton = wx.Button(self, label="Delete")
        actionButtonSizer.Add(self.deleteButton, 0, wx.ALL, 5)
        mainSizer.Add(actionButtonSizer, 0, wx.ALIGN_LEFT | wx.ALL, 5)

        self.closeButton = wx.Button(self, label="Close")
        mainSizer.Add(self.closeButton, 0, wx.ALIGN_RIGHT | wx.ALL, 5)

        self.SetSizer(mainSizer)
        self.Layout()

        self.deleteButton.Hide()
        self.Layout()

        self.checkList.Bind(wx.EVT_CHECKLISTBOX, self.onCheckChanged)
        self.checkList.Bind(wx.EVT_KEY_DOWN, self.onCheckListKeyDown)
        self.selectAllButton.Bind(wx.EVT_BUTTON, self.onSelectAll)
        self.deleteButton.Bind(wx.EVT_BUTTON, self.onDelete)
        self.closeButton.Bind(wx.EVT_BUTTON, self.onClose)

        wx.CallAfter(self.checkList.SetFocus)

    def onCheckListKeyDown(self, event):
        keycode = event.GetKeyCode()
        if keycode == wx.WXK_SPACE:
            index = self.checkList.GetSelection()
            if index != wx.NOT_FOUND:
                newState = not self.checkList.IsChecked(index)
                self.checkList.Check(index, newState)
                self.updateActionButtons()
                ui.message("Checked" if newState else "Not checked")
        else:
            event.Skip()

    def getCheckedIndices(self):
        return [i for i in range(self.checkList.GetCount()) if self.checkList.IsChecked(i)]

    def updateActionButtons(self):
        anyChecked = len(self.getCheckedIndices()) > 0
        self.deleteButton.Show(anyChecked)
        self.Layout()

    def onCheckChanged(self, event):
        self.updateActionButtons()

    def onSelectAll(self, event):
        for i in range(self.checkList.GetCount()):
            self.checkList.Check(i, True)
        self.updateActionButtons()
        ui.message("All items selected")

    def onDelete(self, event):
        indices = self.getCheckedIndices()
        if not indices:
            ui.message("No items selected")
            return
        for i in sorted(indices, reverse=True):
            del self.plugin.passwordEntries[i]
        self.checkList.Set(self.plugin.passwordEntries)
        self.deleteButton.Hide()
        self.Layout()
        ui.message("Deleted " + str(len(indices)) + " item(s)")

    def onClose(self, event):
        self.Close()


class PasswordManagerDialog(wx.Dialog):
    def __init__(self, parent, plugin):
        super(PasswordManagerDialog, self).__init__(parent, title="Password Manager", size=(560, 400))
        self.plugin = plugin
        self.filteredIndices = list(range(len(self.plugin.passwordEntries)))

        mainSizer = wx.BoxSizer(wx.VERTICAL)

        searchLabel = wx.StaticText(self, label="Search:")
        mainSizer.Add(searchLabel, 0, wx.LEFT | wx.TOP, 10)
        self.searchBox = wx.TextCtrl(self)
        mainSizer.Add(self.searchBox, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 10)

        self.listBox = wx.ListBox(self, choices=self.plugin.passwordEntries, style=wx.LB_SINGLE)
        mainSizer.Add(self.listBox, 1, wx.EXPAND | wx.ALL, 10)

        buttonSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.newButton = wx.Button(self, label="New")
        self.manageButton = wx.Button(self, label="Manage")
        self.changePasswordButton = wx.Button(self, label="Change Password")
        self.closeButton = wx.Button(self, label="Close")
        buttonSizer.Add(self.newButton, 0, wx.ALL, 5)
        buttonSizer.Add(self.manageButton, 0, wx.ALL, 5)
        buttonSizer.Add(self.changePasswordButton, 0, wx.ALL, 5)
        buttonSizer.Add(self.closeButton, 0, wx.ALL, 5)
        mainSizer.Add(buttonSizer, 0, wx.ALIGN_CENTER | wx.ALL, 5)

        self.SetSizer(mainSizer)
        self.Layout()

        self.Bind(wx.EVT_CHAR_HOOK, self.onCharHook)
        self.searchBox.Bind(wx.EVT_TEXT, self.onSearchTextChanged)
        self.newButton.Bind(wx.EVT_BUTTON, self.onNew)
        self.manageButton.Bind(wx.EVT_BUTTON, self.onManage)
        self.changePasswordButton.Bind(wx.EVT_BUTTON, self.onChangePassword)
        self.closeButton.Bind(wx.EVT_BUTTON, self.onClose)

        self.searchBox.SetFocus()
        if self.plugin.passwordEntries:
            self.listBox.SetSelection(len(self.plugin.passwordEntries) - 1)

    def onSearchTextChanged(self, event):
        query = self.searchBox.GetValue().strip().lower()
        if not query:
            self.filteredIndices = list(range(len(self.plugin.passwordEntries)))
        else:
            self.filteredIndices = [
                i for i, text in enumerate(self.plugin.passwordEntries)
                if query in text.lower()
            ]
        displayItems = [self.plugin.passwordEntries[i] for i in self.filteredIndices]
        self.listBox.Set(displayItems)
        if displayItems:
            self.listBox.SetSelection(0)

    def onCharHook(self, event):
        keycode = event.GetKeyCode()
        focused = self.FindFocus()
        if keycode in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER) and focused in (self.listBox, self.searchBox):
            self.pasteSelected()
        elif keycode == wx.WXK_ESCAPE:
            self.Close()
        else:
            event.Skip()

    def getSelectedRealIndex(self):
        displayIndex = self.listBox.GetSelection()
        if displayIndex == wx.NOT_FOUND or displayIndex >= len(self.filteredIndices):
            return None
        return self.filteredIndices[displayIndex]

    def pasteSelected(self):
        realIndex = self.getSelectedRealIndex()
        if realIndex is None:
            ui.message("No item selected")
            return
        text = self.plugin.passwordEntries[realIndex]
        api.copyToClip(text)
        self.Close()
        wx.CallLater(500, pasteTextIntoFocus, text)

    def onNew(self, event):
        dlg = AddFavoriteDialog(self, title="Add Password Entry")
        result = dlg.ShowModal()
        if result == wx.ID_OK:
            text = dlg.getText()
            if text:
                self.plugin.passwordEntries.append(text)
                self.plugin.saveData()
                self.filteredIndices = list(range(len(self.plugin.passwordEntries)))
                self.listBox.Set(self.plugin.passwordEntries)
                self.listBox.SetSelection(len(self.plugin.passwordEntries) - 1)
                ui.message("Password entry added")
            else:
                ui.message("No text entered")
        dlg.Destroy()

    def onManage(self, event):
        dlg = PasswordManageDialog(self, self.plugin)
        dlg.ShowModal()
        self.plugin.saveData()
        self.filteredIndices = list(range(len(self.plugin.passwordEntries)))
        self.listBox.Set(self.plugin.passwordEntries)

    def onChangePassword(self, event):
        verifyDlg = PasswordVerifyDialog(self, self.plugin)
        gui.mainFrame.prePopup()
        verifyResult = verifyDlg.ShowModal()
        gui.mainFrame.postPopup()
        verifyDlg.Destroy()

        if verifyResult == wx.ID_OK:
            changeDlg = PasswordChangeDialog(self, self.plugin)
            gui.mainFrame.prePopup()
            changeResult = changeDlg.ShowModal()
            gui.mainFrame.postPopup()
            if changeResult == wx.ID_OK:
                newPass, newHint = changeDlg.getValues()
                changeDlg.Destroy()
                self.plugin.masterPassword = newPass
                self.plugin.passwordHint = newHint
                self.plugin.saveData()
                ui.message("Password and hint updated successfully")
            else:
                changeDlg.Destroy()

    def onClose(self, event):
        self.Close()


class ClipboardHistoryDialog(wx.Dialog):
    def __init__(self, parent, plugin):
        super(ClipboardHistoryDialog, self).__init__(parent, title="Clipboard History", size=(420, 400))
        self.plugin = plugin
        self.filteredIndices = list(range(len(self.plugin.history)))

        mainSizer = wx.BoxSizer(wx.VERTICAL)

        searchLabel = wx.StaticText(self, label="Search:")
        mainSizer.Add(searchLabel, 0, wx.LEFT | wx.TOP, 10)
        self.searchBox = wx.TextCtrl(self)
        mainSizer.Add(self.searchBox, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 10)

        self.listBox = wx.ListBox(self, choices=self.plugin.history, style=wx.LB_SINGLE)
        mainSizer.Add(self.listBox, 1, wx.EXPAND | wx.ALL, 10)

        buttonSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.favoriteButton = wx.Button(self, label="Favorite")
        self.manageButton = wx.Button(self, label="Manage")
        self.passwordManagerButton = wx.Button(self, label="Password Manager")
        self.closeButton = wx.Button(self, label="Close")
        buttonSizer.Add(self.favoriteButton, 0, wx.ALL, 5)
        buttonSizer.Add(self.manageButton, 0, wx.ALL, 5)
        buttonSizer.Add(self.passwordManagerButton, 0, wx.ALL, 5)
        buttonSizer.Add(self.closeButton, 0, wx.ALL, 5)
        mainSizer.Add(buttonSizer, 0, wx.ALIGN_CENTER | wx.ALL, 5)

        self.SetSizer(mainSizer)
        self.Layout()

        self.Bind(wx.EVT_CHAR_HOOK, self.onCharHook)
        self.searchBox.Bind(wx.EVT_TEXT, self.onSearchTextChanged)
        self.closeButton.Bind(wx.EVT_BUTTON, self.onClose)
        self.favoriteButton.Bind(wx.EVT_BUTTON, self.onFavorite)
        self.manageButton.Bind(wx.EVT_BUTTON, self.onManage)
        self.passwordManagerButton.Bind(wx.EVT_BUTTON, self.onPasswordManager)

        self.searchBox.SetFocus()
        if self.plugin.history:
            self.listBox.SetSelection(len(self.plugin.history) - 1)

    def onSearchTextChanged(self, event):
        query = self.searchBox.GetValue().strip().lower()
        if not query:
            self.filteredIndices = list(range(len(self.plugin.history)))
        else:
            self.filteredIndices = [
                i for i, text in enumerate(self.plugin.history)
                if query in text.lower()
            ]
        displayItems = [self.plugin.history[i] for i in self.filteredIndices]
        self.listBox.Set(displayItems)
        if displayItems:
            self.listBox.SetSelection(0)

    def onCharHook(self, event):
        keycode = event.GetKeyCode()
        focused = self.FindFocus()
        if keycode in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER) and focused in (self.listBox, self.searchBox):
            self.pasteSelected()
        elif keycode == wx.WXK_ESCAPE:
            self.Close()
        else:
            event.Skip()

    def getSelectedRealIndex(self):
        displayIndex = self.listBox.GetSelection()
        if displayIndex == wx.NOT_FOUND or displayIndex >= len(self.filteredIndices):
            return None
        return self.filteredIndices[displayIndex]

    def pasteSelected(self):
        realIndex = self.getSelectedRealIndex()
        if realIndex is None:
            ui.message("No item selected")
            return
        text = self.plugin.history[realIndex]
        api.copyToClip(text)
        self.Close()
        wx.CallLater(500, pasteTextIntoFocus, text)

    def onClose(self, event):
        self.Close()

    def onFavorite(self, event):
        realIndex = self.getSelectedRealIndex()
        if realIndex is None:
            ui.message("No item selected")
            return
        text = self.plugin.history[realIndex]
        if text not in self.plugin.favorites:
            self.plugin.favorites.append(text)
            self.plugin.saveData()
            ui.message("Added to favorites")
        else:
            ui.message("Already in favorites")

    def onManage(self, event):
        dlg = ManageDialog(self, self.plugin)
        dlg.ShowModal()
        self.plugin.saveData()
        self.filteredIndices = list(range(len(self.plugin.history)))
        self.listBox.Set(self.plugin.history)

    def onPasswordManager(self, event):
        self.Close()
        wx.CallAfter(self.plugin.openPasswordManagerFlow)


class ManageDialog(wx.Dialog):
    def __init__(self, parent, plugin):
        super(ManageDialog, self).__init__(parent, title="Manage Clipboard History", size=(450, 400))
        self.plugin = plugin

        mainSizer = wx.BoxSizer(wx.VERTICAL)

        self.checkList = wx.CheckListBox(self, choices=self.plugin.history)
        mainSizer.Add(self.checkList, 1, wx.EXPAND | wx.ALL, 10)

        topButtonSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.selectAllButton = wx.Button(self, label="Select All")
        topButtonSizer.Add(self.selectAllButton, 0, wx.ALL, 5)
        mainSizer.Add(topButtonSizer, 0, wx.ALIGN_LEFT | wx.ALL, 5)

        actionButtonSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.backupButton = wx.Button(self, label="Backup")
        self.deleteButton = wx.Button(self, label="Delete")
        actionButtonSizer.Add(self.backupButton, 0, wx.ALL, 5)
        actionButtonSizer.Add(self.deleteButton, 0, wx.ALL, 5)
        mainSizer.Add(actionButtonSizer, 0, wx.ALIGN_LEFT | wx.ALL, 5)

        self.closeButton = wx.Button(self, label="Close")
        mainSizer.Add(self.closeButton, 0, wx.ALIGN_RIGHT | wx.ALL, 5)

        self.SetSizer(mainSizer)
        self.Layout()

        self.backupButton.Hide()
        self.deleteButton.Hide()
        self.Layout()

        self.checkList.Bind(wx.EVT_CHECKLISTBOX, self.onCheckChanged)
        self.checkList.Bind(wx.EVT_KEY_DOWN, self.onCheckListKeyDown)
        self.selectAllButton.Bind(wx.EVT_BUTTON, self.onSelectAll)
        self.backupButton.Bind(wx.EVT_BUTTON, self.onBackup)
        self.deleteButton.Bind(wx.EVT_BUTTON, self.onDelete)
        self.closeButton.Bind(wx.EVT_BUTTON, self.onClose)

        wx.CallAfter(self.checkList.SetFocus)

    def onCheckListKeyDown(self, event):
        keycode = event.GetKeyCode()
        if keycode == wx.WXK_SPACE:
            index = self.checkList.GetSelection()
            if index != wx.NOT_FOUND:
                newState = not self.checkList.IsChecked(index)
                self.checkList.Check(index, newState)
                self.updateActionButtons()
                ui.message("Checked" if newState else "Not checked")
        else:
            event.Skip()

    def getCheckedIndices(self):
        return [i for i in range(self.checkList.GetCount()) if self.checkList.IsChecked(i)]

    def updateActionButtons(self):
        anyChecked = len(self.getCheckedIndices()) > 0
        self.backupButton.Show(anyChecked)
        self.deleteButton.Show(anyChecked)
        self.Layout()

    def onCheckChanged(self, event):
        self.updateActionButtons()

    def onSelectAll(self, event):
        for i in range(self.checkList.GetCount()):
            self.checkList.Check(i, True)
        self.updateActionButtons()
        ui.message("All items selected")

    def onDelete(self, event):
        indices = self.getCheckedIndices()
        if not indices:
            ui.message("No items selected")
            return
        for i in sorted(indices, reverse=True):
            del self.plugin.history[i]
        self.checkList.Set(self.plugin.history)
        self.backupButton.Hide()
        self.deleteButton.Hide()
        self.Layout()
        ui.message("Deleted " + str(len(indices)) + " item(s)")

    def onBackup(self, event):
        indices = self.getCheckedIndices()
        if not indices:
            ui.message("No items selected")
            return
        with wx.FileDialog(
            self,
            "Save backup as",
            wildcard="Text files (*.txt)|*.txt",
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT
        ) as fileDialog:
            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return
            path = fileDialog.GetPath()
            try:
                with open(path, "w", encoding="utf-8") as f:
                    for i in indices:
                        f.write(self.plugin.history[i] + "\n")
                ui.message("Backup saved")
            except Exception:
                ui.message("Could not save backup")

    def onClose(self, event):
        self.Close()
