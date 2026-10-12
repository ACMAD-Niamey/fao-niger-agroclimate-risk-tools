<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis version="3.28" styleCategories="Symbology">
  <pipe>
    <rasterrenderer type="singlebandpseudocolor" band="1" classificationMin="0" classificationMax="3" alphaBand="-1">
      <rastershader>
        <colorrampshader colorRampType="DISCRETE" clip="0" classificationMode="1">
          <item value="0" label="No drought or full recovery" color="#f0f0f0" alpha="255"/>
          <item value="1" label="Watch / partial recovery" color="#fed976" alpha="255"/>
          <item value="2" label="Warning" color="#fd8d3c" alpha="255"/>
          <item value="3" label="Alert" color="#e31a1c" alpha="255"/>
        </colorrampshader>
      </rastershader>
    </rasterrenderer>
  </pipe>
</qgis>
