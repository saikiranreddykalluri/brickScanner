
Meeting Transcript
Speaker 1: In medical claim, you use a number of different columns to link the medical claims, right? So can you scroll up to the incentive? I can explain to you how. So here, you will use all these columns: DW cap payment key, line number, DW member key, sub ID, group sector, group numbers, SR number. You have to kind of get a uniqueness out of this. So here, I don't have a line number in the incentive. So what I've done is I've kept member key as line number. Kind of those things will give me the uniqueness here. So you need to select a uniqueness from out of all these columns. And each source should definitely contain a claim scope name, because that is how you define where this comes from. It can be local, host, cost, like those different kinds of things. And each source will definitely have those names. And now from that, you will filter based on the—like you will rename the columns, right? So if you see line numbers 17 to 22...

Speaker 2: Yeah, yeah.

Speaker 1: So whenever link_claim_number is called, right, it will link based on claim key, incurred date, like those kinds of things. So you have to have claim key, line number, and incurred date to be present there. Or else it won't link properly. I mean, linking won't even happen. That's how we have written the passes. Okay? Now this is kind of how we are seeding into. Now if you look at the function, line number 24, link_claim_number.

Speaker 2: Okay.

Speaker 1: Line number 24. So that is where the main linking happens. If you can understand how this function is defined, you can see how it will be written. Can you search for this?

Speaker 2: Okay. (pause) Yeah.

Speaker 1: Yeah, this function. Okay, can you... so here till 15, 16 lines is how you are defining your input sources. And different pass functions is what you have from all the names of passes, how you are looking. So line number 22 to 28, right? Those are the ones. DW member, group sector, coverage date. Each function will use different kinds of columns to link the medical claims to membership. Now, when you actually call, right... can you take one pass? I'll explain one pass, you can search for that.

Speaker 2: Okay. (pause) Yeah.

Speaker 1: Yeah, so this is the first pass. Okay? What is it doing here? So it is taking your source... line number 8 is your claim source view, right?

Speaker 2: Yes, yes.

Speaker 1: So that is whatever you send in. It can be medical claims, incentive, now we will send encounter here.

Speaker 2: Okay, okay.

Speaker 1: Now you are joining it on different dimensions like dim_corp_entity, group sector, account, dim_date, all these things, and you are taking membership ID, group sector ID from this. Okay? Group sector ID, account... whichever underscore sequence is there, right, from line number 5 to line number 7...

Speaker 2: Yes.

Speaker 1: ...you are taking all those from the dimensions and joining it with the encounter, stuff like that. Okay? So from each pass, if you get a good hit, you will take this function. We have to test it multiple times thoroughly. Like if I am getting a good number of hits from one pass, I'll stop at one pass. If I get a good pass from two passes, I'll stop at two passes. That kind of thing is what we test thoroughly. So this is one pass, right? Can you go up?

Speaker 2: (Navigates screen)

Speaker 1: No, no, no, just scroll up actually.

Speaker 2: Okay.

Speaker 1: Scroll up actually. Yeah, so the top one is the second pass now. Okay? Whatever membership linking that you have done from the previous one, that will stay. Okay? Now this will have a different sequence number. So it will be like membership_id_2. Okay? Now here you will have different membership ID, group sector ID, account ID, network IDs.

Speaker 2: Yeah, yeah.

Speaker 1: So you will do a coalesce of both of those when you get to filter that. And then whichever is having the value, only those you will take to the final formatting. That formatting will be done in the link claim member main original function. Here, this pass is just to define how the membership linking is done. In a similar fashion, you will do like 7 passes.

Speaker 2: Okay.

Speaker 1: Okay, this is what, on a high level, link claim number is doing. In a similar fashion, you need to create a similar function for this. You saw how incentive is being defined, right? For encounter also, you have to use a kind of similar pattern to generate that. Why I haven't touched this logic is because it is too complex for now to define. That is why I haven't touched all this. I wanted to complete all that and come back here.

Speaker 2: Okay. What if, first, we can start creating the membership additional notebook and all, then we can test it and we can improve the things in the skill file? Or we can define it newly. And one more thing is, this notebook is a kind of hardcoded one, or do you want me to take the required functions and keep it in the skill file?

Speaker 1: No, whenever you want to call claim membership linking, right, you have to call this notebook. The entire one. You need the entire one.

Speaker 2: If I use that dot-dot slash syntax that we use to call the claim linking, right? If I keep that cell at the top, will that be fine?

Speaker 1: Yeah, that is fine. Yeah. However you are defining commons and past instances, right, the same method applies there.

Speaker 2: Okay, okay. And for a new source, there is the link notebook... it should get updated here in the claim membership linking notebooks, right?

Speaker 1: It should get updated here in the claim membership linking. So for a new notebook, there should be a new function that is defined. So I have defined incentive, it just came last month. If you see for incentive, I just updated only one cell. So that should take care of the entire claim membership linking.

Speaker 2: Okay.

Speaker 1: Yep, that's how we define. And passes I told you, right?

Speaker 2: What are the other linking notebooks? Are they also required?

Speaker 1: For now, only claim membership linking is enough for whatever we are doing for the source. Yep.

Speaker 2: I mean, I can see those load membership, membership MO, upsert...

Speaker 1: Yeah, all those are only for medical claims, we are not gonna use that. For now, we are using only claim membership linking.

Speaker 2: Okay, cool.

Speaker 1: For your reference, right, how we will use the source, what I can do is I will show you how one table is getting generated. Can you go to the fact tables? In star schema, fact tables.

Speaker 2: Not in denorm tables?

Speaker 1: Yep. Can you open the workflow? You call this notebook like claim membership linking notebook after fact.

Speaker 2: Right. And you pass the source name?

Speaker 1: Yes. Actually, no, we will create... so I'll create a fact notebook, right? The last step of the fact notebook is generating this one. Let me open the incentive one, you will get to know how I did it for incentive and what we are expecting. Yeah, medical membership is also fine. Yeah, sure, open that please.

(Screen sharing pauses/adjusts)

Speaker 2: Shall I stop the screen share?

Speaker 1: No, no, open it.

Speaker 2: Which one? The membership one?

Speaker 1: Open the membership one, yeah. Okay, can you see cell number 6 here?

Speaker 2: Yeah, membership linking.

Speaker 1: Yeah, so this is how I call claim membership linking. Correct. This notebook. And here we are using this. So this is the source that we are passing into it, right?

Speaker 2: Yeah.

Speaker 1: So in the skill file, do we have something like... are we entering any kind of source here? Or do you want me to add that as an additional question to it?

Speaker 2: Yeah, it's better you add that as a question. Every time source changes, right?

Speaker 1: If membership ID is there... I think so far what I've done is if there is any membership ID, then proceed with this. But instead, I think it would be better if I can add one main question like, "Do you want membership linking notebook extra?" so that then we can ask what is the source. And what columns that you want to update.

Speaker 2: Yes, yeah, that is true. You can do it in a similar fashion for that. And also, if it's a different source, right, so medical claims is pretty much straightforward. Okay? You don't need to do much for medical claims because that is how we have defined claim membership linking. But when you come to other sources, right, that is where the tricky part is. So that's why I wanted to open fact_incentive. Can you come here and open fact_incntv? Scroll down, scroll down. You'll have it in the upside part. Yeah, here you will have fact_incntv.

Speaker 2: Yep, that's the one.

Speaker 1: So inside this, you will see how we are defining one. So can you check this one on cell number 6?

Speaker 2: Yeah.

Speaker 1: Are you able to see this read_incentive_data function, right?

Speaker 2: Yes, yes.

Speaker 1: So how we will define this is like... so if you can open the incentive commons, you will have this function defined. Every underscore commons function, if you see in the left side of the notebooks, right, you have incentive_commons, member_character_commons...

Speaker 2: Oh yeah, yeah.

Speaker 1: All underscore commons, is like what we do is you will define how to read the input data. If you see, we are selecting the bronze schema and selecting only particular... we are keeping filters on the data, what all we need to read. Okay? For now, we are only interested in cost data for incentive. So when I come back, I will read only incentive data here. Okay?

Speaker 2: Okay.

Speaker 1: So this is one method we will follow to read the input source for fact. Now, coming to member linking. Now we have a function called incentive_member_linking which I have showed you, like just which I've explained to you on a high level how we are defining that.

Speaker 2: Yes.

Speaker 1: That is supposed to take care of the entire claim member linking.

Speaker 2: Okay.

Speaker 1: Now this we will feed it as an input for fact.

Speaker 2: Okay.

Speaker 1: Yeah, so the same thing we would like to follow for the encounter as well.

Speaker 2: Okay. Only till cell number 7. From cell number 7 is how we were defining how you have to do the upsert thing, right? Instead of fact generation, you wanted to split the data.

Speaker 1: Okay, okay. So, can we tweak the skill file like, based on the source, call a different function for linking?

Speaker 2: Yes. Yeah, generate a different function and define the source, yeah.

Speaker 1: Okay, so one is incentive and another one is claims, and one more is UOC and encounter?

Speaker 2: You have member characteristics, MBR_CHAR_TC. All these are there in the single notebook or in a different...

Speaker 1: For membership linking, only one single notebook, yeah.

Speaker 2: I think if I feed in this notebook and identify the multiple linking sources, then based on it, it will create/call that function directly, right?

Speaker 1: Yes. In the notebook, you have pharmacy there... so if you have like 6 to 7 different sources of membership linking there, it will definitely identify that.

Speaker 2: Okay, okay. Fine.

Speaker 1: So 7 sources we have...

Speaker 2: Sorry, the last part I did not completely get. When you say after this, we need to generate a fact?

Speaker 1: Before, it used to be like this. Now we are following whatever the medical claims is following, Sushant. Before, we used to generate... it used to be membership linking, fact generation. Now what happened is like, first we will do the fact generation, keeping membership ID as -1. Okay? Then we will go back to membership linking, then we will upsert the membership IDs to the fact table.

Speaker 2: Okay. Along with the other columns also, Vamshi? Are we going to keep -1 for the columns that we are selecting while linking?

Speaker 1: Not all columns, only membership ID, because the rest of the columns will be present there. Membership ID is the only thing that is not present. Group sector ID, all these columns are present there already.

Speaker 2: Okay, will that get updated once we've done the linking?

Speaker 1: Yes.

Speaker 2: I mean, if that updates, then can we use -1 for these also? Or can we keep it as it is?

Speaker 1: That's a good question. Again, I am lacking on that technical perspective. I am also getting a question, I will confirm that with Chaitra actually, for the... this is the question, right? Along with membership ID, there are group ID, group sector ID, so you want to keep it as -1 and do that? Yeah, generally we don't do, but let me confirm that, I don't want to take that call.

Speaker 2: Fine.

Speaker 1: Yep. Okay. So what I will document whatever we have spoken now, I'll put it into wordings and I'll give it in the group.

Speaker 2: Yeah, yeah, sure.

Speaker 1: Correct. Yeah, yeah, sure, yeah. So we will discuss... like whatever we have discussed here, let me reiterate again. For the membership linking, there will be a function. Whenever a new source comes in, you have to ask whether this is a different kind of source and what is the name of the source. That is what the skill will ask. You have to generate a new function based on... you have to feed the input of claim membership linking to the AI and then you have to ask to generate a similar function according to the sources. And you have to... so membership linking, right? Once before, the fact generation has to happen and you have to do the fact generation keeping membership ID as -1. Next, you have to do the claim membership linking, and then you have to upsert the membership IDs to the fact table. And this is the entire flow. Now the only question pending on my end is whether to keep only the membership ID as -1 or the other columns which is group ID, group sector ID as -1 as well.

Speaker 2: Yeah. Okay.

Speaker 1: Yeah, this is on a high level, but I will write down all the steps that I have explained to get a better understanding as well.

Speaker 2: Okay, okay. Yeah.

Speaker 1: Okay. Cool. Yep. I think we have covered on this. Yeah. Sure, I will get that and give it to you.

Speaker 2: Sure. Oh, mother side, you pull the changes to the same branch, right?

Speaker 1: Actually I am pulling the changes whenever there are any updates in the branch.

Speaker 2: Okay. Yeah, I mean, make sure you do.
