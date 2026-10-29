from django_components import component


@component.register("footer")
class Footer(component.Component):
    template_file = "footer.html"

    def get_template_data(self, args, kwargs, slots, context):

        return {
            "urls": {
                "articles": kwargs.get("articles_url", "/articles/browse/"),
                "challenges": kwargs.get("challenges_url", "/challenges/"),
                "feed": kwargs.get("feed_url", "/feed/"),
                "donations": kwargs.get("donations_url", "/donations/"),
                "helpdesk": kwargs.get("helpdesk_url", "/helpdesk/tickets/"),
            },
        }
