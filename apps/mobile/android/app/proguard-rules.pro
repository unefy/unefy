# R8 full mode is the default. Add keep rules here only with a comment
# explaining which reflective access requires them.

# ML Kit and Firebase find their components by reading class names out of the
# merged manifest and calling getDeclaredConstructor().newInstance(). The names
# keep the classes alive, but nothing in the program *calls* those constructors,
# so full mode removes them — and discovery only logs the failure:
#
#   W ComponentDiscovery: Could not instantiate
#     com.google.mlkit.vision.barcode.internal.BarcodeRegistrar
#   Caused by: java.lang.NoSuchMethodException: …BarcodeRegistrar.<init> []
#
# The component is then simply absent, MlKitContext.get() hands back null, and
# BarcodeScanning.getClient() dereferences it: the scanner crashed the instant
# it was opened, in release builds and nowhere else.
-keep class * implements com.google.firebase.components.ComponentRegistrar {
    <init>();
}
