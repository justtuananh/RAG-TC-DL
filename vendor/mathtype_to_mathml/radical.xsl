<?xml version="1.0" encoding="UTF-8"?>
<!--
  Bổ sung cho gem mathtype_to_mathml 0.0.7: gem KHÔNG có template cho căn thức
  (MTEF tmROOT), nên XSLT của gem bỏ âm thầm dấu căn cùng toàn bộ biểu thức dưới
  căn (QTKĐ 1.159: mẫu số "\sqrt{2}", "\sqrt{3}" mất, còn "\frac{U(t)}{}").

  Theo đặc tả MTEF 5, tmROOT có hai slot: slot 1 là biểu thức dưới căn, slot 2 là
  chỉ số căn (rỗng với căn bậc hai tvROOT_SQ). ingestion/mtef_to_latex.py nạp file
  này SAU transform.xsl của gem (xsl:import) nên chỉ thêm template, không sửa gem.
-->
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" version="1.0">

    <xsl:template match="tmpl[selector='tmROOT']">
        <msqrt>
            <xsl:apply-templates select="slot[1] | pile[1]"/>
        </msqrt>
    </xsl:template>

    <xsl:template match="tmpl[selector='tmROOT' and variation='tvROOT_NTH']">
        <mroot>
            <xsl:apply-templates select="slot[1] | pile[1]"/>
            <xsl:apply-templates select="slot[2] | pile[2]"/>
        </mroot>
    </xsl:template>

</xsl:stylesheet>
