Now that all the modules is already in sync, i want you to make a major improvement across all modules. You can directly modify, add, improve all the views, urls. models, etc to make all the relevant and necessary improvement. The objective and goal is to provide a better user experience and UI refinement based on 8 Principles on User Interface. Before you decided to improve, add, or improve something, decide wheather its important and highly necessary for the system or not. Use MoSCoW priority model as basis for making a decision. Here i give you priority on what to do (TODO's) for this major changes and after this prompt DO NOT IMMEDIATELY EXECUTE IT, give me your thoughts about these changes to me for confirmation. List of changes:

1. Add a UUIDField for models that currently does not have one and actually needed it (such as feeds, comments, articles, donations, etc.) to ensure data security and integration. This also means you will be updating views, urls, that directly related to database interaction. Execute python manage.py makemigrations and python manage.py migrate yourself. (HIGH PRIORITY)
  
2. Alter models that NEEDED improvements (add more fields for better user informative and informative purpose), make sure you analyze first rather than adding some unneccessary field to a model that is already good and well-designed. Make sure to always run python manage.py makemigrations and python manage.py migrate each time if there are changes in model module. (HIGH PRIORITY)
  

1. Add more features for each of these modules (feeds, articles, donations, and challenges). Here are the list of features that i think needs to implemented:
  

a. Articles: There are major bugs that affect this entire module which is article cant be created, user cant make an article, category dropdown does not show anything (HIGH PRIORITY). Add more features along the way that will likely relates to Challenges module (such as tracking read article count, etc.)

b. Challenges: Wired up everything to track challenges that correlates directly with another module. Admin can assign badge reward when creating challenge so that user get that badge if the challenge is considered completed.
c. Donations: Add tracker that will likely correlates with Challenges (such as spend 100,000 for donations this week or etc.). The rest is pretty good (can leave as-is) but i need you to give your opinion for improving user interface design and populate more with informative and interactive component. (MEDIUM PRIORITY)

d. Feeds: Set maximum photo attach (10) for user upload and 50 for admin upload). Add tracker that will likely correlates with challenges (such as 100 post likes this week, 50 comments this month, etc.). Populate this feed section with more component and more features (you can reference Twitter, Instagram) (MEDIUM PRIORITY)

2. NEW FEATURES
  

- Badge system: This correlates with Challenge and Accounts/Profile module where user can store and collect badges if they completed a challenge. All of the user's acquired badges will be displayed in the profile, user can also choose only 1 badge as a display label beside their name (such as when posting a feed, comments, like)
  
- Liked by: Feed post can track liked_by users and then can display them if the user wants to see their likers. Comments also works this way.
  
- Comment reply: Reference with Instagram or Twitter comment section idea
  
- You can give another features if needed and important (give your thoughts first)
  

NOTE: The output of this prompt is to see your suggestion and thoughts about all of these changes and features, is it really needed?