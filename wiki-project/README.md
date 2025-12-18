# Team wiki-stream

## Team members: Emujin Batzorig & Jia Park



## Data Source

The data source that we chose to work with is the Wikipedia Recent Changes Event Stream which is a real-time data feed of events occurring across the MediaWiki ecosystem. This stream provides a continuous flow of updates including details like the specific type of edit, along with metadata such as the user, page title, timestamp, and language. We accessed this data with Server-Sent Events (SSE) and ingested it into a Kafka topic using a wikipedia producer script. We thought that this data source would be good to work with because it is high-volume, very structured, and provides a good variety of event types, which means we could perform interesting analysis. 


## Challenges / Obstacles

 The first challenge was that the raw events come in nested JSON with lots of optional fields and different types of changes, so we had to carefully parse and filter the data to get the information we wanted (we chose language and change type). There was also an extremely high number of different languages being written on Wikipedia, so we had to filter for only the top 30 to make the plot readable and the analysis stronger. Additionally, because the stream sends in a lot of events, we needed a fast and reliable way to store everything. We solved this by using a Kafka cluster to collect the data and DuckDB to save it for later analysis. Finally, one of the more challenging aspects was working with the JSON fields, which were not very intuitive. For instance, the enwiki tag corresponds to English edits. As a result, we needed to rename or recode several of these fields to make our plots clearer and more interpretable.

## Analysis

Most of the activity in our dataset comes from a few very active Wikimedia projects. Wikimedia Commons, which stores images and media used across all Wikipedias, produces a lot of constant updates as files are uploaded, renamed, or reorganized. Wikidata, the structured database that supports facts and links across Wikipedia pages, also creates many small automated changes. English Wikipedia adds another large share simply because it has the biggest user base. In comparison, smaller language Wikipedias contribute far fewer edits. When we look at the types of actions being recorded, most events are regular edits to existing pages, followed by changes to how pages are categorized or logged by the system. New pages are created much less often. Taken together, the data shows that most of the real-time activity is ongoing maintenance work that keeps these large platforms organized and up-to-date.

## Plot / Visualization

![Description](https://github.com/EmujinBat/wikipedia_analysis/blob/main/type_plot.png)
![Description](https://github.com/EmujinBat/wikipedia_analysis/blob/main/language_plot.png)



## GitHub Repository

https://github.com/EmujinBat/wikipedia_analysis
