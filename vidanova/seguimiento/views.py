from django.shortcuts import render

def seguimiento(request):
    return render(request, 'seguimiento/seguimiento.html')
