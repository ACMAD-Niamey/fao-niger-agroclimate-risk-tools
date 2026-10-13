# The Optional Language Model Description

*Last reviewed: 2026-10-13.* The risk maps and statistics work without any of this. A language model can add a short plain-language description of a finished map, written for a colleague. It is off until you set it up, and nothing is ever sent without asking you first.

## Set it up

On the **Settings** tab:

| Field | What to enter |
| --- | --- |
| Service address | The address of an OpenAI-style chat service, ending in `/v1` (for example `https://your-service.example.org/v1`). The plugin adds `/chat/completions`, so do not type that part |
| Model | The model's name exactly as the service lists it |
| API key | The key for that service. Spaces, line breaks and invisible characters from copy-and-paste are removed for you |
| Extra request fields | Optional. See *Reasoning models* below. Leave empty if unsure |
| Language | English or French |
| Remember the key | Off by default: the key then lives only in memory and is gone when QGIS closes. If ticked, it is stored **unencrypted** in your QGIS profile |

Press **Test connection**. It checks the address, the key and the model one at a time and says which is wrong. It uses what is typed, so you do not have to save first. Then press **Save**.

Any service that speaks the OpenAI chat protocol works, including hosted services and a model running on your own computer or server. The plugin has been tried against a LiteLLM proxy serving a Qwen model.

## Use it

Run a map. On the **Results** tab, press **Describe with the language model**. The plugin shows you which server the figures will go to and asks you to confirm. The description appears in the box below, always ending with a line saying it is a draft that an expert must review.

If you made a region summary first, the region table is included, so the description can say where risk is highest.

## What is sent

Only summary figures, built from a fixed list. Nothing else can be added:

- the period shown, and whether it is older than the one you asked for
- whether the map is the current CDI or the seasonal outlook, and whether only cropland and rangeland were scored
- the class areas and shares, the mean score, the worst class, the scored area
- if you made a region summary, up to 15 regions with: name, scored area, mean score, worst class, the share of area in each class, and the hectares of cropland and rangeland in high-risk cells
- three fixed notes on the map's limits (provisional thresholds, blank areas are not low risk, the seasonal hazard is coarse)

**Never sent:** the rasters, file names or paths, your username or computer, the API key (except to the service as its login), or anything from your other QGIS layers.

## What the model is and is not for

It only puts the computed figures into words. It does not choose classes, thresholds or triggers, and the prompt tells it to use only the numbers it is given, to say that the thresholds are provisional, and not to give operational orders or predict losses. It can still make mistakes in wording, so read every description before using it, and treat it as a draft. For decisions, use the figures and the maps.

## Reasoning models

Some models think at length before answering (for example Qwen models served with vLLM). That can take a minute or more, and they may use up their allowance thinking and give no answer. If you see "The model produced no answer", enter this in **Extra request fields** and try again:

```json
{"chat_template_kwargs": {"enable_thinking": false}}
```

On the model we tried, this cut a description from over a minute (sometimes with no answer) to about 15 seconds. Leave the field empty for services that do not need it: some, such as OpenAI's, reject fields they do not recognise. Answers are streamed, so a service that cuts silent connections after about a minute does not cut a long answer.

## If something goes wrong

| Message | What to check |
| --- | --- |
| The service rejected the API key (HTTP 401) | The key. The message gives the length of the key you entered, its last four characters, and the positions of characters that are easy to mistake (the digit **0** and the capital letter **O**; **1**, lowercase **l** and capital **I**). Compare those with where the key came from. Copy it from the source again |
| The service address was not found (HTTP 404) | The address. It should end with `/v1` and must not contain `/chat/completions` twice. The message shows the exact address the plugin called |
| This key is not allowed (HTTP 403) | That the key may use this model, and that the address is the service's API address |
| The model is not in the service's list | The model name. The message lists the names the service offers |
| The service did not accept the request (HTTP 400) | The model name, and the Extra request fields |
| The model produced no answer | Turn thinking off, as above |
| The Extra request fields are not valid | They must be a JSON object in double quotes, or empty |
| Limiting requests (HTTP 429), or a problem on the service's side (HTTP 5xx) | Wait and try again |
| Could not reach the service | The address and your internet connection |

The plugin never shows the service's own error text, because services often include parts of the key in it.
