from django.db import migrations, models


def split_admin_role(apps, schema_editor):
    """
    将原有 admin 角色拆分：
    - Django superuser → 保留为 admin（系统管理员）
    - 其余 → 改为 property（物业管理员）
    """
    UserProfile = apps.get_model('accounts', 'UserProfile')
    User = apps.get_model('auth', 'User')
    for profile in UserProfile.objects.filter(role='admin'):
        if User.objects.filter(pk=profile.user_id, is_superuser=True).exists():
            profile.role = 'admin'
        else:
            profile.role = 'property'
        profile.save(update_fields=['role'])


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_merge_property_into_admin"),
    ]

    operations = [
        migrations.RunPython(split_admin_role, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="userprofile",
            name="role",
            field=models.CharField(
                choices=[("resident", "居民"), ("property", "物业管理员"), ("admin", "系统管理员")],
                default="resident",
                max_length=20,
                verbose_name="角色",
            ),
        ),
    ]
