from django.shortcuts import render

def login(request):
    return render(request, 'login.html')
def seguimiento(request):
    return render(request, 'seguimiento.html')