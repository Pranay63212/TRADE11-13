# Roman Numeral Anniversary Sweatshirt: listing + setup

## 1. Etsy listing (copy and paste)

**Title** (135/140 characters)
```
Personalized Anniversary Sweatshirt, Roman Numeral Date & Initials, Valentines Day Gift for Her, Custom Couples Crewneck, Gift for Wife
```

**13 tags** (each 20 characters or fewer)
```
anniversary hoodie, roman numeral date, couples sweatshirt, valentines for her, gift for girlfriend, gift for wife, personalized hoodie, initials sweatshirt, custom date shirt, anniversary gift, matching couples, wedding date gift, est date sweatshirt
```

**Description**
```
Turn your special day into something she can wear every day.

This personalized sweatshirt features your initials in elegant script and the date that matters most (the day you met, your first date, or your wedding day) in classic Roman numerals.

HOW TO ORDER
1. Choose your size and color.
2. In the personalization box, enter:
   - Two initials (example: J & A)
   - Your date as MM/DD/YYYY (example: 02/14/2020)
3. Add to cart.

We double-check every Roman numeral before printing.

DETAILS
- Unisex fit crewneck sweatshirt (sizes run unisex, so women may want to size down for a fitted look)
- Soft cotton/polyester blend
- Design printed on the front

PRODUCTION & SHIPPING
- Made to order just for you
- Production: [X] business days, then shipping: [X] business days
- VALENTINE'S DAY: order by [DATE] for delivery by Feb 14

CARE
Machine wash cold, inside out. Tumble dry low. Do not iron directly on the design.

Because each item is personalized, we can't accept returns for change of mind, but if anything arrives damaged or wrong, message us and we'll make it right.
```
Before publishing, fill in every [X] and [DATE] using Printify's real production and shipping times. Check the fabric blend and care details against the Printify product page too.

**Personalization box** (turn on "Personalization" in the Etsy listing)
- Instructions to buyer: `Enter 2 initials and your date as MM/DD/YYYY. Example: J & A, 02/14/2020`
- Make it required: yes

**Price**: $39.99 with free shipping (profit about $10 per sale at the estimated costs; recheck with real Printify prices)

## 2. Setup steps (one time)

1. **Printify** → Catalog → search "Gildan 18000" (Unisex Heavy Blend Crewneck Sweatshirt).
2. Pick a print provider. Compare price, shipping cost and rating.
3. Upload `output/JA_2020-02-14_black.png` as the **front** design (it's the sample placeholder). Center it on the chest.
4. Colors: offer only light colors (e.g., white, sand, light pink) with the black design. If you want dark colors (black, navy), make a second listing with the white design.
5. Set the price ($39.99) and publish to Etsy.
6. On Etsy, paste the title, tags and description above, and turn on Personalization.
7. Use Printify's mockups for photos. Once you have a sample, replace them with your own photos.

## 3. When an order comes in (each time)

1. Read the buyer's initials and date in the Etsy order.
2. Send them to Claude, or run the script yourself:
   `python3 make_design.py --initials J A --date 2020-02-14`
   (add `--color white` for dark sweatshirts)
3. In Printify, open the order **before it goes to production** and replace the sample design with the new file.
   [Unverified] Printify may send orders to production automatically. Check its settings for **manual order approval** and turn it on, so placeholder designs never get printed.
4. Double-check the date, then approve the order.

## 4. Notes
- Fonts: Great Vibes and Cormorant Garamond, both under the SIL Open Font License (license files in `fonts/`). [Unverified] My understanding is that OFL allows commercial use on products. Read the license files to confirm.
- In the Great Vibes font, the capital "A" looks a bit like a lowercase "a". That's how the font draws it. If it bothers you, I can swap in a different script font.
