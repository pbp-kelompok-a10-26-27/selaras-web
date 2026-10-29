from django_components import component


@component.register("pagination")
class Pagination(component.Component):
    template_file = "pagination.html"

    def get_template_data(self, args, kwargs, slots, context):
        page_obj = kwargs.get("page_obj")
        param = kwargs.get("param", "page")
        anchor = kwargs.get("anchor", "")
        request = context.get("request")

        if page_obj is None or page_obj.paginator.num_pages <= 1:
            return {"show": False}

        def url_for(number):
            query = request.GET.copy() if request else {}
            query[param] = number
            return f"?{query.urlencode()}{anchor}"

        items = []
        for entry in page_obj.paginator.get_elided_page_range(
            page_obj.number, on_each_side=1, on_ends=1
        ):
            if isinstance(entry, int):
                items.append(
                    {
                        "number": entry,
                        "url": url_for(entry),
                        "current": entry == page_obj.number,
                    }
                )
            else:
                items.append({"ellipsis": True})

        return {
            "show": True,
            "items": items,
            "page_number": page_obj.number,
            "total_pages": page_obj.paginator.num_pages,
            "previous_url": url_for(page_obj.previous_page_number())
            if page_obj.has_previous()
            else "",
            "next_url": url_for(page_obj.next_page_number())
            if page_obj.has_next()
            else "",
            "class_": kwargs.get("class_", ""),
        }
