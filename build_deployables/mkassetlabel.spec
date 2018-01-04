# -*- mode: python -*-

block_cipher = None


a = Analysis(['../AssetLabelGenerator/mkassetlabel.py'],
             pathex=['/Users/alex/Dropbox/Projects/python/Asset-Label-Generator/build_deployables'],
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
          exclude_binaries=True,
          name='mkassetlabel',
          debug=False,
          strip=False,
          upx=True,
          console=True )
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               name='mkassetlabel')
