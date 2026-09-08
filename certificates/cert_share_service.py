"""
绿证份额管理服务

统一封装 CertShare 的创建、冻结、解冻、转移、删除逻辑，
避免散落在多个 views / commands / services 中。
"""

from django.db import transaction
from django.db.models import Sum

from .models import GreenCertificate, CertShare
from accounts.models import UserProfile


# ────────────────────────────────────────────
#  分配（绿证生成时按面积比例分配给居民）
# ────────────────────────────────────────────

def distribute_shares(cert: GreenCertificate) -> list[CertShare]:
    """
    按居住面积比例将绿证份额分配给已审核居民。

    最后一位居民获得剩余全部份额，确保 total_shares 不因取整而丢失。
    """
    residents = UserProfile.objects.filter(
        role='resident', is_verified=True, area__gt=0,
    )
    total_area = residents.aggregate(s=Sum('area'))['s']
    if not total_area:
        return []

    created: list[CertShare] = []
    remaining = cert.total_shares
    resident_list = list(residents)

    for i, profile in enumerate(resident_list):
        if i == len(resident_list) - 1:
            share_amount = remaining
        else:
            share_amount = int(cert.total_shares * profile.area / total_area)
            remaining -= share_amount

        if share_amount > 0:
            cs = CertShare.objects.create(
                certificate=cert, owner=profile.user,
                amount=share_amount, source='initial',
            )
            created.append(cs)

    return created


# ────────────────────────────────────────────
#  冻结 / 解冻（卖单相关）
# ────────────────────────────────────────────

def freeze_shares(user, cert: GreenCertificate, amount: int) -> None:
    """
    冻结用户指定证书的 amount 份可用份额。

    按获得时间从早到晚依次冻结；若某条份额数大于所需，则拆分。
    """
    remaining = amount
    shares = CertShare.objects.filter(
        owner=user, certificate=cert, is_frozen=False,
    ).order_by('acquired_at')

    for s in shares:
        if remaining <= 0:
            break
        if s.amount <= remaining:
            s.is_frozen = True
            s.save()
            remaining -= s.amount
        else:
            # 拆分：未冻结部分留下，冻结部分新建/标记
            CertShare.objects.create(
                certificate=cert, owner=user,
                amount=s.amount - remaining, source=s.source,
            )
            s.amount = remaining
            s.is_frozen = True
            s.save()
            remaining = 0


def unfreeze_shares(user, cert: GreenCertificate, amount: int) -> None:
    """
    解冻用户指定证书的 amount 份冻结份额。

    按获得时间从晚到早依次解冻；若某条份额数大于所需，则拆分。
    """
    to_unfreeze = amount
    frozen = CertShare.objects.filter(
        owner=user, certificate=cert, is_frozen=True,
    ).order_by('-acquired_at')

    for fs in frozen:
        if to_unfreeze <= 0:
            break
        if fs.amount <= to_unfreeze:
            fs.is_frozen = False
            fs.save()
            to_unfreeze -= fs.amount
        else:
            # 拆分：冻结部分保留，解冻部分新建
            CertShare.objects.create(
                certificate=cert, owner=user,
                amount=fs.amount - to_unfreeze, source=fs.source, is_frozen=True,
            )
            fs.amount = to_unfreeze
            fs.is_frozen = False
            fs.save()
            to_unfreeze = 0


# ────────────────────────────────────────────
#  转移（交易成交时）
# ────────────────────────────────────────────

def transfer_frozen_shares(seller, buyer, cert: GreenCertificate,
                           amount: int) -> CertShare:
    """
    从卖方冻结份额中扣除 amount 份，为买方新建对应份额。

    返回买方新建的 CertShare。
    """
    remaining = amount
    frozen = CertShare.objects.filter(
        owner=seller, certificate=cert, is_frozen=True,
    ).order_by('acquired_at')

    for fs in frozen:
        if remaining <= 0:
            break
        if fs.amount <= remaining:
            remaining -= fs.amount
            fs.delete()
        else:
            fs.amount -= remaining
            fs.save()
            remaining = 0

    return CertShare.objects.create(
        certificate=cert, owner=buyer, amount=amount, source='trade',
    )


# ────────────────────────────────────────────
#  删除（绿证过期时）
# ────────────────────────────────────────────

def delete_shares_by_cert(cert: GreenCertificate) -> int:
    """删除指定绿证下的所有份额，返回删除数量。"""
    count, _ = CertShare.objects.filter(certificate=cert).delete()
    return count


# ────────────────────────────────────────────
#  查询辅助
# ────────────────────────────────────────────

def get_available_shares(user, cert: GreenCertificate) -> int:
    """获取用户在某张证书下的可用（未冻结）份额总数。"""
    return CertShare.objects.filter(
        owner=user, certificate=cert, is_frozen=False,
    ).aggregate(s=Sum('amount'))['s'] or 0


def get_frozen_shares(user, cert: GreenCertificate) -> int:
    """获取用户在某张证书下的冻结份额总数。"""
    return CertShare.objects.filter(
        owner=user, certificate=cert, is_frozen=True,
    ).aggregate(s=Sum('amount'))['s'] or 0
