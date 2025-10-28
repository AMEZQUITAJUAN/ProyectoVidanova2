from django.shortcuts import render

def followups(request):
    return render(request, 'followups.html')
