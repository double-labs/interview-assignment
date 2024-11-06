# Assignment

This is a frontend related assignment, but not in the usual sense.
The agent related front-end work is more low level than usual. 
Instead of dealing with high level abstractions and frameworks, you'll have to figure out low level interactions that aren't working as expected.
This assignment is focused on seeing if you can find your way using the developer tools to find low level problems.

You will be trying to solve frontend related problems we either have solved or are still in the process of solving while tackling the popular benchmark, [Workarena](https://github.com/ServiceNow/WorkArena)


# Setup 

```bash
# make sure this is in the current working directory
git clone git@github.com:ServiceNow/BrowserGym.git
```

```bash
python -m venv venv 
source venv/bin/activate
pip install -r requirements.txt
playwright install
```

```bash
python main.py
```

This will start the chrome browser with a task setup. 
No actual agent is running so nothing will happen. 

If for whatever reason the page can't be found or something, comment out the page.goto() line and find the ipad page manually.
Don't hesitate to ask, it would be a shame if you lose time on this.

## Task related information 

After loading, you can see a page with a table.
The workarena task was for the agent to filter the table based on certain columns.

Once everything is setup, clicking enter will parse the whole page. 
You can recognize it worked after a second because a new AXT file will pop up in the results/folder.
If you update the page, clicking enter will parse it again and create an AXT in the results folder.

## Questions 

Read the questions below. 
They are about things we encounter daily in the context of the AXT.
Try to be clear but stay concise. 
Play around with the parsing and have a good look at the resulting AXT's from the html.

1. In the task there is a "show/hide" filter button, once you click it, some dropdowns will appear. After clicking on the dropdown, the agent often got stuck. 
What could be the problem? How did you approach debugging it? Do you have an idea how to solve it?

2. A big problem we are facing with this task, is the fact that the AXT is not very clear for the agent. 
Once opening the dropdown, it doesn't often choose the correct next steps. 
Study the HTML elements and the AXT. 
How could we improve the AXT to make it more clear for the agent what it should interact with and what it should avoid?
Hint: We are thinkign of using more aria attributes, which ones could be useful and how?

3. A common problem we see is that inputs are marked as interactable, but clicking on them or typing into them does not do anything.
When trying to debug this, some of the parent elements are actually interactable.
However, they don't have any obvious interactable attributes (onclick etc).
They also don't have any EventListeners. 
How exactly is this interaction being recorded?
How can we improve our interactable element detection to account for this?
