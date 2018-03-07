# -*- mode: python -*-

block_cipher = None


a = Analysis(['mkassetlabel.py'],
             pathex=['/Users/alex/Dropbox/Projects/python/Asset-Label-Generator/AssetLabelGenerator'],
             binaries=[],
             datas=[],
             hiddenimports=['_sysconfigdata_m'],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          name='mkassetlabel',
          debug=False,
          strip=False,
          upx=True,
          runtime_tmpdir=None,
          console=True )
