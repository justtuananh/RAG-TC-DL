"""Sinh 20 biên bản kiểm định áp kế pittông theo QTKĐ 1.159:2021.

Gói này gồm:

- ``spec_data``: soạn toàn bộ số liệu "sự thật" một cách tất định;
- ``xlsx_patch``: vá ô trực tiếp trên OOXML của tệp mẫu bằng ``zipfile`` + ``lxml``;
- ``build``: vá mẫu, tính lại công thức bằng LibreOffice headless, ghi tệp + manifest.
"""
