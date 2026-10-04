from django.shortcuts import render

def design_system(request):
    from django.shortcuts import render


def design_system(request):
    primary_colors = [
        {"name": "50", "value": "#f7f9f0"},
        {"name": "100", "value": "#f2f6e9"},
        {"name": "200", "value": "#e5edd2"},
        {"name": "300", "value": "#aac46d"},
        {"name": "400", "value": "#99b062"},
        {"name": "500", "value": "#889d57"},
        {"name": "600", "value": "#809352"},
        {"name": "700", "value": "#667641"},
        {"name": "800", "value": "#4c5831"},
        {"name": "900", "value": "#3b4526"},
    ]

    secondary_colors = [
        {"name": "50", "value": "#eff2ed"},
        {"name": "100", "value": "#e7ebe5"},
        {"name": "200", "value": "#cdd6c8"},
        {"name": "300", "value": "#5f7a4f"},
        {"name": "400", "value": "#566e47"},
        {"name": "500", "value": "#4c623f"},
        {"name": "600", "value": "#475c3b"},
        {"name": "700", "value": "#39492f"},
        {"name": "800", "value": "#2b3724"},
        {"name": "900", "value": "#212b1c"},
    ]

    tertiary_colors = [
        {"name": "50", "value": "#fef9fa"},
        {"name": "100", "value": "#fdf6f8"},
        {"name": "200", "value": "#fbedf0"},
        {"name": "300", "value": "#f3c5cf"},
        {"name": "400", "value": "#dbb1ba"},
        {"name": "500", "value": "#c29ea6"},
        {"name": "600", "value": "#b6949b"},
        {"name": "700", "value": "#92767c"},
        {"name": "800", "value": "#6d595d"},
        {"name": "900", "value": "#554548"},
    ]

    neutral_colors = [
        {"name": "50", "value": "#fffffe"},
        {"name": "100", "value": "#fffffe"},
        {"name": "200", "value": "#fffefd"},
        {"name": "300", "value": "#fffdf8"},
        {"name": "400", "value": "#e6e4df"},
        {"name": "500", "value": "#cccac6"},
        {"name": "600", "value": "#bfbeba"},
        {"name": "700", "value": "#999895"},
        {"name": "800", "value": "#737270"},
        {"name": "900", "value": "#595957"},
    ]

    return render(
        request,
        "design/design_system.html",
        {
            "primary_colors": primary_colors,
            "secondary_colors": secondary_colors,
            "tertiary_colors": tertiary_colors,
            "neutral_colors": neutral_colors,
        },
    )