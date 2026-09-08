"""初始化演示数据：创建用户、设备、发电记录、绿证等"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from accounts.models import UserProfile
from certificates.models import PVDevice, PowerRecord, GreenCertificate, CertShare
from certificates.cert_share_service import distribute_shares, freeze_shares, get_available_shares, transfer_frozen_shares
from trading.models import Order, Trade
from blockchain.services import add_block
from django.utils import timezone
from datetime import timedelta, date
import random


class Command(BaseCommand):
    help = '初始化社区绿证系统演示数据'

    def handle(self, *args, **options):
        self.stdout.write('正在初始化演示数据...')

        # 创建系统管理员
        admin_user, _ = User.objects.get_or_create(username='admin', defaults={'is_staff': True, 'is_superuser': True})
        admin_user.set_password('admin123456')
        admin_user.save()
        UserProfile.objects.get_or_create(user=admin_user, defaults={
            'role': 'admin', 'phone': '13800000000', 'points': 99999, 'is_verified': True,
        })

        # 创建物业管理员
        property_user, _ = User.objects.get_or_create(username='property', defaults={'is_staff': True})
        property_user.set_password('property123456')
        property_user.save()
        UserProfile.objects.get_or_create(user=property_user, defaults={
            'role': 'property', 'phone': '13800000001', 'points': 99999, 'is_verified': True,
        })

        # 创建居民用户
        residents = []
        resident_data = [
            ('linhao', '1栋1单元101', 89.5),
            ('suyan', '1栋1单元201', 105.2),
            ('liujia', '1栋2单元301', 78.0),
            ('zhaoyang', '2栋1单元102', 120.0),
            ('sunmeng', '2栋1单元202', 95.3),
            ('zhouxin', '2栋2单元301', 110.0),
            ('wutong', '3栋1单元101', 85.0),
            ('zhengfei', '3栋1单元201', 92.0),
        ]
        for uname, unit, area in resident_data:
            u, _ = User.objects.get_or_create(username=uname)
            u.set_password('user12345')
            u.save()
            p, _ = UserProfile.objects.get_or_create(user=u, defaults={
                'role': 'resident', 'unit_number': unit, 'area': area,
                'phone': f'138{random.randint(10000000,99999999)}',
                'points': 10000, 'is_verified': True,
            })
            residents.append(u)

        # 创建光伏设备
        devices_data = [
            ('屋顶光伏板A组', '1号楼', 50.0, date(2023, 6, 1)),
            ('屋顶光伏板B组', '1号楼', 40.0, date(2023, 8, 15)),
            ('屋顶光伏板C组', '2号楼', 60.0, date(2024, 1, 10)),
            ('屋顶光伏板D组', '3号楼', 45.0, date(2024, 3, 20)),
            ('屋顶光伏板E组', '4号楼', 55.0, date(2024, 7, 1)),
            ('屋顶光伏板F组', '5号楼', 48.0, date(2024, 9, 15)),
            ('屋顶光伏板G组', '2号楼', 35.0, date(2025, 2, 10)),
            ('屋顶光伏板H组', '3号楼', 52.0, date(2025, 5, 20)),
            ('屋顶光伏板I组', '4号楼', 42.0, date(2025, 8, 1)),
            ('屋顶光伏板J组', '5号楼', 58.0, date(2025, 11, 15)),
            ('屋顶光伏板K组', '1号楼', 38.0, date(2026, 1, 5)),
            ('屋顶光伏板L组', '6号楼', 65.0, date(2026, 3, 10)),
        ]
        devices = []
        for name, building, cap, inst_date in devices_data:
            d, _ = PVDevice.objects.get_or_create(
                name=name, building=building,
                defaults={'capacity_kw': cap, 'installed_date': inst_date},
            )
            devices.append(d)

        # 为每个设备生成过去12个月的发电记录（从安装日期起）
        today = date.today()
        for device in devices:
            start_date = max(device.installed_date, today - timedelta(days=365))
            days_span = (today - start_date).days
            for i in range(days_span + 1):
                d = start_date + timedelta(days=i)
                if PowerRecord.objects.filter(device=device, date=d).exists():
                    continue
                max_kwh = device.capacity_kw * 5
                # 夏季发电量更高
                month = d.month
                season_factor = 0.5 + 0.5 * (1 + (6 - abs(month - 7)) / 6) / 2
                kwh = round(random.uniform(max_kwh * 0.3, max_kwh * 0.9) * season_factor, 1)
                PowerRecord.objects.create(
                    device=device, date=d, kwh=kwh, recorder=property_user,
                )

        # 生成绿证（每1000kWh生成1张），按设备按月份分散生成，使份额获取时间分散
        from django.db.models import Sum
        from django.db.models.functions import TruncMonth
        for device in devices:
            # 按月统计发电量，绿证在对应月份生成
            monthly = PowerRecord.objects.filter(
                device=device, is_valid=True,
            ).annotate(month=TruncMonth('date')).values('month').annotate(
                total_kwh=Sum('kwh'),
            ).order_by('month')
            cumulative = 0
            for entry in monthly:
                cumulative += entry['total_kwh']
                cert_month = entry['month']
                # 该月之前已有的绿证数
                existing = GreenCertificate.objects.filter(device=device).count()
                while cumulative - existing * 1000 >= 1000:
                    cert = GreenCertificate(device=device, total_kwh=1000, total_shares=1000)
                    cert.save()
                    # 份额获取时间设为该月中旬的随机时间
                    import datetime as dt
                    mid_month = cert_month.replace(day=15) + dt.timedelta(days=random.randint(-5, 5))
                    mid_month_dt = timezone.make_aware(
                        dt.datetime.combine(mid_month, dt.time(
                            random.randint(8, 18), random.randint(0, 59), random.randint(0, 59)
                        ))
                    )
                    share_time = min(mid_month_dt, timezone.now())
                    share_details = []
                    for cs in distribute_shares(cert):
                        share_details.append({
                            'owner': cs.owner.username,
                            'amount': cs.amount,
                            'unit': cs.owner.profile.unit_number,
                        })
                        # 覆盖 acquired_at 为对应月份时间
                        CertShare.objects.filter(pk=cs.pk).update(acquired_at=share_time)
                    add_block({
                        'type': 'cert_generation',
                        'description': '绿证生成并分配份额存证',
                        'cert_id': cert.cert_id,
                        'device': str(device),
                        'device_capacity_kw': device.capacity_kw,
                        'device_status': device.get_status_display(),
                        'kwh': 1000,
                        'total_shares': 1000,
                        'share_distribution': share_details,
                        'timestamp': share_time.isoformat(),
                    })
                    existing += 1

        cert_count = GreenCertificate.objects.count()

        # 创建交易挂单演示数据
        order_count = 0
        active_certs = list(GreenCertificate.objects.filter(status='active')[:6])
        if active_certs and len(residents) >= 4:
            # zhangsan 卖出挂单
            for cert in active_certs[:2]:
                avail = get_available_shares(residents[0], cert)
                if avail > 0:
                    sell_shares = min(avail, random.randint(30, 80))
                    freeze_shares(residents[0], cert, sell_shares)
                    sell_price = round(random.uniform(8, 15), 1)
                    Order.objects.get_or_create(
                        user=residents[0], certificate=cert, order_type='sell',
                        defaults={
                            'shares': sell_shares,
                            'price_per_share': sell_price,
                            'status': 'pending',
                            'expire_time': timezone.now() + timedelta(days=random.randint(3, 14)),
                        },
                    )
                    add_block({
                        'type': 'order_create',
                        'description': '卖出挂单上链存证',
                        'order_type': 'sell',
                        'user': residents[0].username,
                        'unit': residents[0].profile.unit_number,
                        'cert_id': cert.cert_id,
                        'shares': sell_shares,
                        'price_per_share': sell_price,
                        'total_value': round(sell_shares * sell_price, 1),
                        'timestamp': timezone.now().isoformat(),
                    })
                    order_count += 1

            # lisi 卖出挂单
            for cert in active_certs[2:4]:
                avail = get_available_shares(residents[1], cert)
                if avail > 0:
                    sell_shares = min(avail, random.randint(20, 60))
                    freeze_shares(residents[1], cert, sell_shares)
                    sell_price = round(random.uniform(9, 16), 1)
                    Order.objects.get_or_create(
                        user=residents[1], certificate=cert, order_type='sell',
                        defaults={
                            'shares': sell_shares,
                            'price_per_share': sell_price,
                            'status': 'pending',
                            'expire_time': timezone.now() + timedelta(days=random.randint(5, 10)),
                        },
                    )
                    add_block({
                        'type': 'order_create',
                        'description': '卖出挂单上链存证',
                        'order_type': 'sell',
                        'user': residents[1].username,
                        'unit': residents[1].profile.unit_number,
                        'cert_id': cert.cert_id,
                        'shares': sell_shares,
                        'price_per_share': sell_price,
                        'total_value': round(sell_shares * sell_price, 1),
                        'timestamp': timezone.now().isoformat(),
                    })
                    order_count += 1

            # wangwu 买入挂单
            for cert in active_certs[1:3]:
                price = round(random.uniform(10, 18), 1)
                buy_shares = random.randint(30, 70)
                buyer_profile = residents[2].profile
                cost = int(buy_shares * price)
                if buyer_profile.points >= cost:
                    buyer_profile.points -= cost
                    buyer_profile.save()
                    Order.objects.get_or_create(
                        user=residents[2], certificate=cert, order_type='buy',
                        defaults={
                            'shares': buy_shares,
                            'price_per_share': price,
                            'status': 'pending',
                            'expire_time': timezone.now() + timedelta(days=random.randint(2, 7)),
                        },
                    )
                    add_block({
                        'type': 'order_create',
                        'description': '买入挂单上链存证',
                        'order_type': 'buy',
                        'user': residents[2].username,
                        'unit': residents[2].profile.unit_number,
                        'cert_id': cert.cert_id,
                        'shares': buy_shares,
                        'price_per_share': price,
                        'frozen_points': int(buy_shares * price),
                        'timestamp': timezone.now().isoformat(),
                    })
                    order_count += 1

            # zhaoliu 买入挂单
            for cert in active_certs[3:5]:
                price = round(random.uniform(10, 17), 1)
                buy_shares = random.randint(25, 55)
                buyer_profile = residents[3].profile
                cost = int(buy_shares * price)
                if buyer_profile.points >= cost:
                    buyer_profile.points -= cost
                    buyer_profile.save()
                    Order.objects.get_or_create(
                        user=residents[3], certificate=cert, order_type='buy',
                        defaults={
                            'shares': buy_shares,
                            'price_per_share': price,
                            'status': 'pending',
                            'expire_time': timezone.now() + timedelta(days=random.randint(3, 12)),
                        },
                    )
                    add_block({
                        'type': 'order_create',
                        'description': '买入挂单上链存证',
                        'order_type': 'buy',
                        'user': residents[3].username,
                        'unit': residents[3].profile.unit_number,
                        'cert_id': cert.cert_id,
                        'shares': buy_shares,
                        'price_per_share': price,
                        'frozen_points': int(buy_shares * price),
                        'timestamp': timezone.now().isoformat(),
                    })
                    order_count += 1

        # 创建历史成交记录（过去12个月每月都有）
        trade_count = 0
        active_certs_all = list(GreenCertificate.objects.filter(status='active'))
        if len(residents) >= 6 and len(active_certs_all) >= 3:
            for month_offset in range(11, -1, -1):
                trade_date = timezone.now() - timedelta(days=30 * month_offset)
                trades_this_month = random.randint(2, 5)
                for _ in range(trades_this_month):
                    cert = random.choice(active_certs_all)
                    seller = random.choice(residents[:4])
                    buyer = random.choice(residents[4:])
                    if seller == buyer:
                        continue
                    avail = get_available_shares(seller, cert)
                    if avail <= 0:
                        continue
                    trade_shares = min(avail, random.randint(10, 50))
                    trade_price = round(random.uniform(8, 18), 1)
                    total_price = round(trade_shares * trade_price, 1)
                    freeze_shares(seller, cert, trade_shares)
                    transfer_frozen_shares(seller, buyer, cert, trade_shares)
                    # 积分转移
                    seller_profile = seller.profile
                    buyer_profile = buyer.profile
                    cost = int(total_price)
                    if buyer_profile.points >= cost:
                        buyer_profile.points -= cost
                        buyer_profile.save()
                        seller_profile.points += cost
                        seller_profile.save()
                    # 创建已成交的买卖挂单
                    buy_order = Order.objects.create(
                        user=buyer, order_type='buy', certificate=cert,
                        shares=trade_shares, price_per_share=trade_price,
                        filled_shares=trade_shares, status='filled',
                        expire_time=trade_date + timedelta(days=1),
                    )
                    sell_order = Order.objects.create(
                        user=seller, order_type='sell', certificate=cert,
                        shares=trade_shares, price_per_share=trade_price,
                        filled_shares=trade_shares, status='filled',
                        expire_time=trade_date + timedelta(days=1),
                    )
                    block = add_block({
                        'type': 'trade',
                        'buyer': buyer.username,
                        'seller': seller.username,
                        'cert_id': cert.cert_id,
                        'shares': trade_shares,
                        'price': trade_price,
                        'total': total_price,
                        'timestamp': trade_date.isoformat(),
                    })
                    trade_obj = Trade.objects.create(
                        buy_order=buy_order,
                        sell_order=sell_order,
                        buyer=buyer,
                        seller=seller,
                        certificate=cert,
                        shares=trade_shares,
                        price_per_share=trade_price,
                        total_price=total_price,
                        block_hash=block.hash,
                    )
                    # 覆盖 auto_now_add 的 created_at 为历史时间
                    Trade.objects.filter(pk=trade_obj.pk).update(created_at=trade_date)
                    trade_count += 1

        block_count = add_block({
            'type': 'system_init',
            'message': '系统初始化完成',
            'total_devices': len(devices),
            'total_users': len(residents) + 2,
            'total_certs': cert_count,
            'total_orders': order_count,
            'buildings': sorted(set(d.building for d in devices)),
            'initiator': 'admin',
            'timestamp': timezone.now().isoformat(),
        })

        self.stdout.write(self.style.SUCCESS(
            f'初始化完成！\n'
            f'  用户: admin/admin123456 (系统管理员), property/property123456 (物业管理员), linhao~zhengfei/user12345 (居民)\n'
            f'  设备: {len(devices)} 台\n'
            f'  发电记录: {PowerRecord.objects.count()} 条\n'
            f'  绿证: {cert_count} 张\n'
            f'  挂单: {order_count} 笔\n'
            f'  成交: {trade_count} 笔\n'
            f'  区块: {block_count.index + 1} 个'
        ))
