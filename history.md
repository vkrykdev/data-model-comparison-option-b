# The story behind the demo

Picture a mid-sized industrial-supplies distributor — the kind of business that keeps factories,
contractors, and maintenance crews stocked with the unglamorous-but-essential stuff: rocker
switches, solenoid valves, hydraulic hoses, terminal blocks, stretch wrap. For years it ran on a
clean, well-behaved ERP. Sales, inventory, products, suppliers — all in one tidy system, all
speaking the same language of SKUs and snake_case columns. Life was orderly.

Then the business did what growing businesses do: it spread out.

First, it built a **service department** — technicians opening work orders and consuming spare
parts in the field. Useful, but it lived in its own little system that referred to everything by
`ITM-` codes instead of SKUs. Then came a **helpdesk SaaS** for customer support, where agents
typed product names by hand into tickets — so "Titan Rocker Switch" might show up spelled three
different ways, or left blank entirely. Then the company started selling on the **MegaMart
marketplace**, which had its own listing IDs, its own order feed, and — crucially — took a ~14%
cut, so the money that landed in the bank never matched the gross sales number on the screen.

And then, the big one: on **February 1st, 2026**, it acquired **Lakeside Supply Co.**, a scrappy
regional outfit running on legacy Access and Excel. Lakeside counted stock once a week instead of
daily, wrote its dates the British way (DD/MM/YYYY) as plain text, used its own `LSP-` product
codes, and stocked a bunch of store-brand items the parent company had never carried.

So now leadership has five different systems all describing pieces of one business — and **no
single source of truth.** Someone in finance keeps a `sku_xref_master` spreadsheet that maps the
codes across systems, but it's about 95% complete: a few products were never mapped, one's
retired, a couple have conflicting entries.

Here's the tension that drives everything: **the executives want combined answers now** — total
company sales including Lakeside and the marketplace, which products generate the most complaints,
how the acquired stores are performing — but the integration project that would actually unify the
data is months away. They can't wait.

That's the whole point of the demo. The *same* messy, multi-source reality gets handed to AI
agents, and we watch what happens. A bare agent over the raw tables stumbles — it reports gross
instead of net, can't join free-text product names, misreads "03/02/2026" as March 2nd instead of
February 3rd, and quietly invents numbers when sources won't connect. A properly modeled,
AI-described version of that *same data* answers cleanly and honestly. The company's mess isn't a
bug in the story — **it's the realistic starting condition every real company is in**, and the
demo proves that modeling (and, in the experiment, rich agent instructions) is what turns that
mess into trustworthy answers.
