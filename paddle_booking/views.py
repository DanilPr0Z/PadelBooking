from django.shortcuts import render

def home(request):
    return render(request, 'home.html')

def news(request):
    return render(request, 'news.html')

def booking_page(request):
    return render(request, 'booking.html')

def tournaments(request):

    return render(request, 'tournaments.html')