from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum
from blockchain.models import Block
from blockchain.services import verify_chain


@login_required
def block_list(request):
    blocks = Block.objects.order_by('-index')[:50]
    chain_valid = verify_chain()
    return render(request, 'blockchain/block_list.html', {
        'blocks': blocks, 'chain_valid': chain_valid,
    })


@login_required
def verify_chain_view(request):
    """管理员一键验证区块链完整性"""
    if request.user.profile.role != 'admin':
        messages.error(request, '仅系统管理员可执行链验证')
        return redirect('blockchain:block_list')

    is_valid = verify_chain()
    total_blocks = Block.objects.count()
    if is_valid:
        messages.success(request, f'区块链验证通过，共 {total_blocks} 个区块，数据完整无误')
    else:
        messages.error(request, f'区块链验证失败！共 {total_blocks} 个区块，检测到数据篡改')
    return redirect('blockchain:block_list')


@login_required
def block_detail(request, index):
    block_obj = Block.objects.get(index=index)
    return render(request, 'blockchain/block_detail.html', {'block_obj': block_obj})
