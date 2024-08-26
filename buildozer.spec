[app]
title = Face Recognition App
package.name = kivy
package.domain = com.example
source.dir = .
source.include_exts = py,json,png,jpg,kv,atlas
version = 0.404
requirements = python3,kivy,sdl2_ttf,pillow,kivymd,cython,face_recognition,opencv-python,facenet-pytorch
presplash.filename = %(source.dir)s/data/presplash.png
icon.filename = %(source.dir)s/data/icon.png
orientation = portrait
osx.python_version = 3.12.4
osx.kivy_version = 2.3.0
fullscreen = 0
android.permissions = CAMERA, WRITE_EXTERNAL_STORAGE, INTERNET
android.api = 35
android.minapi = 21
android.ndk = 25b
android.ndk_api = 21
android.enable_androidx = True
android.gradle_dependencies = 'com.google.firebase:firebase-analytics:17.2.1'
android.archs = arm64-v8a, armeabi-v7a
android.allow_backup = True
android.copy_libs = 1
target = android

[buildozer]
log_level = 0
warn_on_root = 1
