from django.contrib import admin
from models import Package, PackageRevision, Module, Attachment, SDK


class PackageAdmin(admin.ModelAdmin):
    pass
admin.site.register(Package, PackageAdmin)


class PackageRevisionAdmin(admin.ModelAdmin):
    pass
admin.site.register(PackageRevision, PackageRevisionAdmin)


class ModuleAdmin(admin.ModelAdmin):
    pass
admin.site.register(Module, ModuleAdmin)


class AttachmentAdmin(admin.ModelAdmin):
    pass
admin.site.register(Attachment, AttachmentAdmin)


class SdkAdmin(admin.ModelAdmin):
    pass
admin.site.register(SDK, SdkAdmin)
