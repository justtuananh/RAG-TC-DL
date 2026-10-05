# Vá gem mathtype_to_mathml 0.0.7 khi chạy, không sửa gem đã cài.
# ingestion/mtef_to_latex.py nạp file này TRƯỚC khi tạo Converter.
#
# 1. Căn thức: gem không có template XSLT cho MTEF tmROOT, nên bỏ âm thầm dấu căn
#    cùng biểu thức dưới căn ("\frac{U(t)}{}" thay vì "\frac{U(t)}{\sqrt{2}}").
#    radical.xsl bổ sung template, nạp sau transform.xsl của gem bằng xsl:import.
# 2. Ngoặc lồng nhau: Mover gắn chỉ số trên / dưới vào cụm ngoặc đứng trước (hoặc
#    sau, với chỉ số đứng trước) nhưng ghép ngoặc mở / đóng GẦN NHẤT, không đếm
#    độ lồng, nên "(U(p))^2" thành "(U)(p)^2". Bản vá tìm ngoặc khớp theo độ lồng.
# 3. Chỉ số "đứng trước" (tvSU_PRECEDES) ở cuối slot, không có gì phía sau để gắn:
#    MathType hiển thị nó như chỉ số thường của ký tự đứng trước (QTKĐ 1.159
#    "A_{0t}"), còn gem dựng mmultiscripts rỗng và ra "A0t". Bản vá bỏ cờ
#    tvSU_PRECEDES của các chỉ số này để chúng gắn vào ký tự đứng trước.
# 4. Gem mathtype 0.0.8 mở OLE ở chế độ "rb+" (ghi) dù chỉ đọc và không đóng file:
#    .bin chỉ đọc (container ghi với chủ root) báo EACCES, công thức thành "không đọc
#    được". Bản vá mở "rb" và đóng ngay sau khi đọc luồng "Equation Native".

require "mathtype_to_mathml"

module QtkdMathTypePatch
  RADICAL_XSL = File.join(__dir__, "radical.xsl")

  module MathtypeReadOnlyPatch
    def initialize(equation)
      eq = Ole::Storage.open(equation, "rb") { |ole| ole.file.read("Equation Native")[28..-1] }
      data = Mathtype::Equation.read(eq).snapshot
      @builder = Nokogiri::XML::Builder.new do |xml|
        @xml = xml
        xml.root do
          process(object: data)
        end
      end
    end
  end

  module ConverterPatch
    def initialize(mathtype)
      super
      wrapper = <<~XSL
        <xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
          <xsl:import href="#{path_to_xslt}"/>
          <xsl:include href="#{RADICAL_XSL}"/>
        </xsl:stylesheet>
      XSL
      @xslt = Nokogiri::XSLT::Stylesheet.parse_stylesheet_doc(Nokogiri::XML(wrapper))
    end
  end

  module MoverPatch
    OPEN_CODES = %w[0x0028 0x005B 0x007B].freeze   # ( [ {
    CLOSE_CODES = %w[0x0029 0x005D 0x007D].freeze  # ) ] }

    def fence_depth_step(node, opening, closing)
      return 0 unless node.name == "char"

      code = node.at_xpath("mt_code_value")&.text
      return 1 if opening.include?(code)
      return -1 if closing.include?(code)

      0
    end

    # Cụm ngoặc khớp bắt đầu từ ``siblings.first`` (đọc theo thứ tự ``siblings``),
    # hoặc chỉ phần tử đầu khi nó không phải ngoặc / ngoặc không khớp.
    def fenced_group(siblings, opening, closing)
      first = siblings.first
      return [first] if fence_depth_step(first, opening, closing) != 1

      depth = 0
      siblings.each_with_index do |node, i|
        depth += fence_depth_step(node, opening, closing)
        return siblings[0..i] if depth.zero?
      end
      [first]
    end

    def wrap_base(el, nodes)
      slot = Nokogiri::XML::Node.new "slot", mathtype
      nodes.each { |node| node.parent = slot }
      el.at_css("slot").add_previous_sibling slot
    end

    def move
      mathtype.xpath("//tmpl[(#{self.class::SUBSUP_SELECTOR}) and #{self.class::PRE}]").each do |el|
        el.xpath("variation[text()='tvSU_PRECEDES']").each(&:remove) if new_following_siblings(el).empty?
      end
      super
    end

    def move_following_subsup
      mathtype.xpath("//tmpl[(#{self.class::SUBSUP_SELECTOR}) and not(#{self.class::PRE})]").each do |el|
        siblings = new_preceding_siblings(el).to_a
        next if siblings.empty?

        wrap_base(el, fenced_group(siblings.reverse, CLOSE_CODES, OPEN_CODES).reverse)
      end
    end

    def move_preceding_subsup
      mathtype.xpath("//tmpl[(#{self.class::SUBSUP_SELECTOR}) and #{self.class::PRE}]").each do |el|
        siblings = new_following_siblings(el).to_a
        next if siblings.empty?

        wrap_base(el, fenced_group(siblings, OPEN_CODES, CLOSE_CODES))
      end
    end
  end
end

Mathtype::Converter.prepend(QtkdMathTypePatch::MathtypeReadOnlyPatch)
MathTypeToMathML::Converter.prepend(QtkdMathTypePatch::ConverterPatch)
MathTypeToMathML::Mover.prepend(QtkdMathTypePatch::MoverPatch)
