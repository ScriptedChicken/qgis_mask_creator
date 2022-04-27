# -*- coding: utf-8 -*-
"""
/***************************************************************************
 MaskCreator
                                 A QGIS plugin
 Creates a mask that surrounds all features within a map.
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                              -------------------
        begin                : 2022-04-16
        git sha              : $Format:%H$
        copyright            : (C) 2022 by Angus Hunt
        email                : angusfhunt@gmail.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QMessageBox
from qgis.core import QgsProject, QgsFillSymbol,QgsVectorLayer, QgsGeometry, QgsFeature
import processing
import json

# Initialize Qt resources from file resources.py
from .resources import *
# Import the code for the dialog
from .mask_creator_dialog import MaskCreatorDialog
import os.path


class MaskCreator:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'MaskCreator_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&Mask Creator')

        # Check if plugin was started the first time in current QGIS session
        # Must be set in initGui() to survive plugin reloads
        self.first_start = None

    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('MaskCreator', message)


    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            # Adds plugin icon to Plugins toolbar
            self.iface.addToolBarIcon(action)

        if add_to_menu:
            self.iface.addPluginToMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_path = ':/plugins/mask_creator/icon.png'
        self.add_action(
            icon_path,
            text=self.tr(u'Create mask'),
            callback=self.run,
            parent=self.iface.mainWindow())

        # will be set False in run()
        self.first_start = True


    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr(u'&Mask Creator'),
                action)
            self.iface.removeToolBarIcon(action)
    
    def loadMask(self):
        crs = QgsProject.instance().crs().authid()
        uri = f"multipolygon?crs={crs}&field=id:integer"
        layer = QgsVectorLayer(uri, "AoI", "memory")

        rect = self.iface.mapCanvas().extent()
        geom = QgsGeometry.fromRect(rect)
        print(geom)

        ftr = QgsFeature(layer.fields())
        ftr.setGeometry(geom)
        ftr.setAttribute("id",0) 
        layer.dataProvider().addFeature(ftr)
        
        res = processing.run("native:difference", {
            'INPUT': layer,\
            'OVERLAY': self.featureBuffer,\
            'OUTPUT': "TEMPORARY_OUTPUT"
        })
        self.mask = res["OUTPUT"]

    def createMask(self):
        vectorLayers = []
        if self.maskBufferValue > 0:
            for l in self.layers:
                try:
                    res = processing.run("native:buffer", {
                        'INPUT': l,\
                        'DISTANCE': self.maskBufferValue,\
                        'SEGMENTS': 5,\
                        'END_CAP_STYLE': 0,\
                        'JOIN_STYLE': 0,\
                        'MITER_LIMIT': 2,\
                        'DISSOLVE': False,\
                        'OUTPUT': "TEMPORARY_OUTPUT"
                    })
                    output = res["OUTPUT"]
                    vectorLayers.append(output)
                except:
                    pass
        
        else:
            for l in self.layers:
                print(type(l))
                if type(l) == QgsVectorLayer:
                    vectorLayers.append(l)

        if len(vectorLayers) > 1:
            res = processing.run("native:mergevectorlayers", {
                'LAYERS': vectorLayers,\
                'CRS': QgsProject.instance().crs(),\
                'OUTPUT': "TEMPORARY_OUTPUT"
            })
            output = res["OUTPUT"]
        else:
            output = vectorLayers[0]

        res = processing.run("native:fixgeometries", {
            'INPUT': output,\
            'OUTPUT': "TEMPORARY_OUTPUT"
        })
        output = res["OUTPUT"]
        print('fixgeometries')

        res = processing.run("native:dissolve", {
            'INPUT': output,\
            'FIELD': None,\
            'OUTPUT': "TEMPORARY_OUTPUT"
        })

        self.featureBuffer = res["OUTPUT"]

        # create mask
        self.loadMask()

        symbolLayer = self.mask.renderer().symbol().symbolLayer(0)
        props = symbolLayer.properties()
        props["color"] = self.maskColour
        self.mask.renderer().setSymbol(QgsFillSymbol.createSimple(props))

        # show the changes
        self.mask.triggerRepaint()

        QgsProject.instance().addMapLayer(self.mask)

    def checkTotalFeatureCount(self):
        lyrs = self.iface.mapCanvas().layers()
        for lyr in lyrs:
            try:
                print(f"{lyr}: {lyr.featureCount()}")
                self.totalFeatureCount += lyr.featureCount()
            except:
                print(f"Couldn't get feature count for {lyr.name()}")
                pass

    def updateMaskBufferValue(self):
        print("Updating mask buffer value")
        value = self.dlg.maskBufferSlider.value()
        self.maskBufferValue = int(value)
        if value == 0:
            text = 'No buffer'
        else:
            text = f"{value}m"
        self.dlg.maskBufferValue.setText(text)
        print(self.dlg.maskBufferValue.text())
    
    def updateMaskStyle(self, band, value):
        style = self.styleSheet
        style[band] = value
        styleString = f"background-color: rgba({style['red']}, {style['green']}, {style['blue']}, {style['alpha']})"
        self.dlg.maskPolygonExample.setStyleSheet(styleString)
        self.maskColour = f"{style['red']},{style['green']},{style['blue']},{style['alpha']}"
        print(self.maskColour)

    def run(self):
        """Run method that performs all the real work"""

        # Create the dialog with elements (after translation) and keep reference
        # Only create GUI ONCE in callback, so that it will only load when the plugin is started
        if self.first_start == True:
            self.first_start = False
            self.dlg = MaskCreatorDialog()
            self.styleSheet = {'red':'', 'green': '', 'blue': '', 'alpha': ''}
            self.updateMaskStyle('red', 0)
            self.updateMaskStyle('green', 0)
            self.updateMaskStyle('blue', 0)
            self.updateMaskStyle('alpha', 128)

        self.project = QgsProject.instance()
        self.layers = self.iface.mapCanvas().layers()
        self.totalFeatureCount = 0
        self.maskBufferValue = 0

        # update slider values
        self.dlg.maskBufferSlider.valueChanged.connect(lambda:self.updateMaskBufferValue())
        self.dlg.maskBufferSlider.setValue(30)

        self.dlg.maskColourSliderRed.valueChanged.connect(lambda:self.updateMaskStyle('red', self.dlg.maskColourSliderRed.value()))
        self.dlg.maskColourSliderGreen.valueChanged.connect(lambda:self.updateMaskStyle('green', self.dlg.maskColourSliderGreen.value()))
        self.dlg.maskColourSliderBlue.valueChanged.connect(lambda:self.updateMaskStyle('blue', self.dlg.maskColourSliderBlue.value()))
        self.dlg.maskColourSliderAlpha.valueChanged.connect(lambda:self.updateMaskStyle('alpha', self.dlg.maskColourSliderAlpha.value()))


        # show the dialog
        self.dlg.show()
        # Run the dialog event loop
        result = self.dlg.exec_()
        # See if OK was pressed

        print(result)

        if result:
            self.checkTotalFeatureCount()
            print(self.totalFeatureCount)
            if len(self.layers) == 0:
                QMessageBox.information(None, "Error", "You have no layers in your project. Please add some and try again.") 
                self.run()
            elif self.totalFeatureCount <= 0:
                QMessageBox.information(None, "Error", "You have no features in your project. Please check any filters on the project's layers and try again.") 
                self.run()
            else:
                self.createMask()
            # Do something useful here - delete the line containing pass and
            # substitute with your code.
            # pass
