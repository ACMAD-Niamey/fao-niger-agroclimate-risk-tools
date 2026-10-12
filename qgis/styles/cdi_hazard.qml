<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis version="3.28" styleCategories="Symbology">
  <pipe>
    <rasterrenderer type="singlebandpseudocolor" band="1" classificationMin="0" classificationMax="3" alphaBand="-1">
      <rastershader>
        <colorrampshader colorRampType="DISCRETE" clip="0" classificationMode="1">
          <item value="0" label="No drought or full recovery" color="#2ca25f" alpha="255"/>
          <item value="1" label="Watch / partial recovery" color="#fee08b" alpha="255"/>
          <item value="2" label="Warning" color="#fdae61" alpha="255"/>
          <item value="3" label="Alert" color="#d73027" alpha="255"/>
        </colorrampshader>
      </rastershader>
    </rasterrenderer>
  </pipe>
</qgis>
