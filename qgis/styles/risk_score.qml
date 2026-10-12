<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis version="3.28" styleCategories="Symbology">
  <pipe>
    <rasterrenderer type="singlebandpseudocolor" band="1" classificationMin="0" classificationMax="3" alphaBand="-1">
      <rastershader>
        <colorrampshader colorRampType="INTERPOLATED" clip="0" classificationMode="1">
          <item value="0" label="0 low" color="#2c7bb6" alpha="255"/>
          <item value="1" label="1 moderate threshold" color="#abd9e9" alpha="255"/>
          <item value="1.7" label="1.7 high threshold" color="#ffffbf" alpha="255"/>
          <item value="2.4" label="2.4 very high threshold" color="#fdae61" alpha="255"/>
          <item value="3" label="3 maximum" color="#d7191c" alpha="255"/>
        </colorrampshader>
      </rastershader>
    </rasterrenderer>
  </pipe>
</qgis>
