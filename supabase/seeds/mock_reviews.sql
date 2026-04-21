-- ============================================================
-- Mock Data: Reviews, Responses, and Insights
-- Requires migration 002_phase1_reviews.sql already applied
-- ============================================================
-- Businesses:
--   f02560b2  Test Business 001  Restaurant  Milton
--   e56bcb43  Test Business 002  Other       Ottawa
--   7f0d69ee  Test 003 clinic    Clinic      Milton
-- ============================================================

-- Mark all 3 test businesses as onboarding complete
UPDATE businesses SET onboarding_completed = true WHERE id IN (
    'f02560b2-1ca4-416e-a866-04b9eb9cf69b',
    'e56bcb43-e709-49bf-a058-0eb605c6fe57',
    '7f0d69ee-a946-4821-b16c-843c34ff06f5'
);


-- ─── BUSINESS 001: Test Business 001 — Restaurant, Milton ────────────────────

INSERT INTO reviews (id, business_id, google_review_id, author, rating, text, review_date, status) VALUES

('b1000000-0000-0000-0000-000000000001', 'f02560b2-1ca4-416e-a866-04b9eb9cf69b', 'gmock_b1_001',
 'Maria Santos', 5,
 'Best Italian food in Milton! The pasta is absolutely divine and the staff are incredibly friendly. Been coming here for 3 years and it never disappoints.',
 NOW() - INTERVAL '2 days', 'responded'),

('b1000000-0000-0000-0000-000000000002', 'f02560b2-1ca4-416e-a866-04b9eb9cf69b', 'gmock_b1_002',
 'David Chen', 4,
 'Really good food, service was a bit slow during busy hours but overall a great experience. Will definitely return!',
 NOW() - INTERVAL '5 days', 'pending'),

('b1000000-0000-0000-0000-000000000003', 'f02560b2-1ca4-416e-a866-04b9eb9cf69b', 'gmock_b1_003',
 'Jennifer Walsh', 5,
 'Celebrated my anniversary here last night. The ambiance was perfect, food was outstanding. Highly recommend the tiramisu!',
 NOW() - INTERVAL '8 days', 'responded'),

('b1000000-0000-0000-0000-000000000004', 'f02560b2-1ca4-416e-a866-04b9eb9cf69b', 'gmock_b1_004',
 'Bob Thompson', 2,
 'Waited 45 minutes for our food on a Tuesday night. Not acceptable. Food was decent but the wait killed the experience.',
 NOW() - INTERVAL '12 days', 'pending'),

('b1000000-0000-0000-0000-000000000005', 'f02560b2-1ca4-416e-a866-04b9eb9cf69b', 'gmock_b1_005',
 'Aisha Mohammed', 5,
 'My go-to restaurant for family dinners. Kids love it too. Great value for money.',
 NOW() - INTERVAL '15 days', 'pending'),

('b1000000-0000-0000-0000-000000000006', 'f02560b2-1ca4-416e-a866-04b9eb9cf69b', 'gmock_b1_006',
 'Pierre Leblanc', 4,
 'Très bon restaurant! Service courtois et nourriture délicieuse. Je recommande le risotto.',
 NOW() - INTERVAL '20 days', 'pending'),

('b1000000-0000-0000-0000-000000000007', 'f02560b2-1ca4-416e-a866-04b9eb9cf69b', 'gmock_b1_007',
 'Sarah Kim', 1,
 'Found a hair in my salad. Staff weren''t apologetic at all. Very disappointing. Won''t be returning.',
 NOW() - INTERVAL '25 days', 'pending'),

('b1000000-0000-0000-0000-000000000008', 'f02560b2-1ca4-416e-a866-04b9eb9cf69b', 'gmock_b1_008',
 'James Murphy', 5,
 'Outstanding! The chef really knows what they''re doing. Fresh ingredients, perfect seasoning. This is what dining should be.',
 NOW() - INTERVAL '30 days', 'responded'),

('b1000000-0000-0000-0000-000000000009', 'f02560b2-1ca4-416e-a866-04b9eb9cf69b', 'gmock_b1_009',
 'Lisa Brown', 3,
 'Average experience. Nothing special but nothing terrible. Food was okay, price was a bit high for the portion size.',
 NOW() - INTERVAL '40 days', 'ignored'),

('b1000000-0000-0000-0000-00000000000a', 'f02560b2-1ca4-416e-a866-04b9eb9cf69b', 'gmock_b1_010',
 'Priya Patel', 5,
 'Amazing! We ordered the tasting menu and every single dish was perfect. Highly recommend for special occasions.',
 NOW() - INTERVAL '45 days', 'pending'),

('b1000000-0000-0000-0000-00000000000b', 'f02560b2-1ca4-416e-a866-04b9eb9cf69b', 'gmock_b1_011',
 'Marco Rossi', 5,
 'Authentic flavors, warm atmosphere. Reminds me of restaurants back in Italy. The owner clearly has a passion for food.',
 NOW() - INTERVAL '55 days', 'pending'),

('b1000000-0000-0000-0000-00000000000c', 'f02560b2-1ca4-416e-a866-04b9eb9cf69b', 'gmock_b1_012',
 'Rachel Green', 4,
 'Lovely spot for a date night. Menu is extensive and the wine selection is impressive. Slightly pricey but worth it.',
 NOW() - INTERVAL '65 days', 'pending');


-- ─── BUSINESS 002: Test Business 002 — Ottawa ─────────────────────────────────

INSERT INTO reviews (id, business_id, google_review_id, author, rating, text, review_date, status) VALUES

('b2000000-0000-0000-0000-000000000001', 'e56bcb43-e709-49bf-a058-0eb605c6fe57', 'gmock_b2_001',
 'Alex Turner', 5,
 'Excellent service! Very professional team. Took care of everything quickly. Would highly recommend to anyone in Ottawa.',
 NOW() - INTERVAL '3 days', 'responded'),

('b2000000-0000-0000-0000-000000000002', 'e56bcb43-e709-49bf-a058-0eb605c6fe57', 'gmock_b2_002',
 'Sophie Gagnon', 4,
 'Bon service dans l''ensemble. Quelques délais mais le personnel était sympathique et serviable.',
 NOW() - INTERVAL '7 days', 'pending'),

('b2000000-0000-0000-0000-000000000003', 'e56bcb43-e709-49bf-a058-0eb605c6fe57', 'gmock_b2_003',
 'Mike Johnson', 2,
 'Not impressed. Communication was very poor and the follow-up took over a week. Expected better professionalism.',
 NOW() - INTERVAL '14 days', 'pending'),

('b2000000-0000-0000-0000-000000000004', 'e56bcb43-e709-49bf-a058-0eb605c6fe57', 'gmock_b2_004',
 'Fatima Hassan', 5,
 'Fantastic experience from start to finish. Very satisfied with the results. Will be using them again for sure.',
 NOW() - INTERVAL '18 days', 'pending'),

('b2000000-0000-0000-0000-000000000005', 'e56bcb43-e709-49bf-a058-0eb605c6fe57', 'gmock_b2_005',
 'Robert Clark', 5,
 'Top-notch professional service. I''ve been a customer for 2 years and I always leave satisfied. Highly trusted.',
 NOW() - INTERVAL '22 days', 'responded'),

('b2000000-0000-0000-0000-000000000006', 'e56bcb43-e709-49bf-a058-0eb605c6fe57', 'gmock_b2_006',
 'Emma Wilson', 3,
 'Decent service but could improve response times. Staff are friendly but overall processes seem slow.',
 NOW() - INTERVAL '30 days', 'ignored'),

('b2000000-0000-0000-0000-000000000007', 'e56bcb43-e709-49bf-a058-0eb605c6fe57', 'gmock_b2_007',
 'Kevin Nguyen', 4,
 'Good quality work and fair pricing. The team was transparent about timelines. Would use again.',
 NOW() - INTERVAL '38 days', 'pending'),

('b2000000-0000-0000-0000-000000000008', 'e56bcb43-e709-49bf-a058-0eb605c6fe57', 'gmock_b2_008',
 'Amanda Foster', 1,
 'Terrible experience. Nobody called me back for over a week despite multiple follow-ups. Very unprofessional.',
 NOW() - INTERVAL '50 days', 'pending');


-- ─── BUSINESS 003: Test 003 Clinic — Milton ──────────────────────────────────

INSERT INTO reviews (id, business_id, google_review_id, author, rating, text, review_date, status) VALUES

('b3000000-0000-0000-0000-000000000001', '7f0d69ee-a946-4821-b16c-843c34ff06f5', 'gmock_b3_001',
 'Michelle Taylor', 5,
 'The entire staff are wonderful. Very compassionate and thorough. Finally found a clinic I trust completely. Dr. Smith is exceptional.',
 NOW() - INTERVAL '1 day', 'responded'),

('b3000000-0000-0000-0000-000000000002', '7f0d69ee-a946-4821-b16c-843c34ff06f5', 'gmock_b3_002',
 'Tom Bradley', 5,
 'Quick appointment, thorough examination, clear explanations. Exactly what you want from a healthcare provider.',
 NOW() - INTERVAL '6 days', 'pending'),

('b3000000-0000-0000-0000-000000000003', '7f0d69ee-a946-4821-b16c-843c34ff06f5', 'gmock_b3_003',
 'Nancy Liu', 4,
 'Professional and caring staff. Wait times can be a bit long but the quality of care is absolutely worth it.',
 NOW() - INTERVAL '10 days', 'pending'),

('b3000000-0000-0000-0000-000000000004', '7f0d69ee-a946-4821-b16c-843c34ff06f5', 'gmock_b3_004',
 'Carlos Rivera', 5,
 'Excellent clinic! Clean, modern facilities and the doctors are very knowledgeable. Highly recommended to everyone in Milton.',
 NOW() - INTERVAL '16 days', 'responded'),

('b3000000-0000-0000-0000-000000000005', '7f0d69ee-a946-4821-b16c-843c34ff06f5', 'gmock_b3_005',
 'Laura Fitzgerald', 2,
 'Had trouble getting an appointment. The phone system is frustrating and I waited 3 weeks for a routine checkup. Needs improvement.',
 NOW() - INTERVAL '21 days', 'pending'),

('b3000000-0000-0000-0000-000000000006', '7f0d69ee-a946-4821-b16c-843c34ff06f5', 'gmock_b3_006',
 'Abdul Rahman', 5,
 'Amazing care! The doctor took time to explain everything clearly. I never feel rushed here. This is how healthcare should be.',
 NOW() - INTERVAL '28 days', 'pending'),

('b3000000-0000-0000-0000-000000000007', '7f0d69ee-a946-4821-b16c-843c34ff06f5', 'gmock_b3_007',
 'Diane Morrison', 3,
 'Average clinic. Gets the job done but nothing exceptional. Staff are professional but not particularly warm or welcoming.',
 NOW() - INTERVAL '35 days', 'ignored'),

('b3000000-0000-0000-0000-000000000008', '7f0d69ee-a946-4821-b16c-843c34ff06f5', 'gmock_b3_008',
 'Steven Park', 5,
 'Best clinic in Milton! I''ve been going here for years and have always received exceptional, personalized care.',
 NOW() - INTERVAL '42 days', 'pending'),

('b3000000-0000-0000-0000-000000000009', '7f0d69ee-a946-4821-b16c-843c34ff06f5', 'gmock_b3_009',
 'Claire Beaumont', 4,
 'Very clean and well-organized. The nurse was kind and the doctor was knowledgeable. Satisfied with my visit.',
 NOW() - INTERVAL '55 days', 'pending');


-- ─── Review Responses (for all 'responded' reviews) ──────────────────────────

INSERT INTO review_responses (id, review_id, ai_draft, final_response, status, edit_ai_score, posted_at) VALUES

-- Business 001 responses
('cc000000-0000-0000-0000-000000000001', 'b1000000-0000-0000-0000-000000000001',
 'Thank you so much, Maria! We are thrilled to hear that you have been enjoying our food for 3 years. Our team works hard every day to bring authentic flavors to your table. We look forward to welcoming you back soon!',
 'Thank you so much, Maria! We''re thrilled you''ve been a loyal guest for 3 years — that means the world to us. Our team truly appreciates your kind words. We look forward to welcoming you back very soon!',
 'posted', 0.92, NOW() - INTERVAL '1 day'),

('cc000000-0000-0000-0000-000000000002', 'b1000000-0000-0000-0000-000000000003',
 'Thank you, Jennifer! Anniversaries are very special and we are so happy we could make yours memorable. Our tiramisu is definitely a favourite! Please visit us again.',
 'Thank you so much, Jennifer! We''re so glad your anniversary dinner was everything you hoped for. You''re right about the tiramisu — it''s made fresh daily! Hope to see you back for your next special occasion.',
 'posted', 0.88, NOW() - INTERVAL '7 days'),

('cc000000-0000-0000-0000-000000000003', 'b1000000-0000-0000-0000-000000000008',
 'James, thank you for this wonderful review! The chef will be very happy to hear your feedback. We are committed to using only the freshest ingredients. See you again soon!',
 'James, thank you for this wonderful review! We''ll pass along your compliments to our chef — it truly makes a difference. We''re proud of our commitment to fresh, quality ingredients. See you soon!',
 'posted', 0.90, NOW() - INTERVAL '29 days'),

-- Business 002 responses
('cc000000-0000-0000-0000-000000000004', 'b2000000-0000-0000-0000-000000000001',
 'Thank you, Alex! We appreciate your trust in our team. Providing efficient and professional service is our top priority. We look forward to working with you again.',
 'Thank you for the kind words, Alex! We''re glad our team could deliver the professional experience you expected. Looking forward to working with you again!',
 'posted', 0.87, NOW() - INTERVAL '2 days'),

('cc000000-0000-0000-0000-000000000005', 'b2000000-0000-0000-0000-000000000005',
 'Thank you for your continued loyalty, Robert! Two years means a lot to us. We will keep working hard to earn your trust.',
 'Robert, two years and counting — that means the world to us! Thank you for your continued trust. We''ll keep working hard to deliver the service you deserve.',
 'posted', 0.93, NOW() - INTERVAL '21 days'),

-- Business 003 responses
('cc000000-0000-0000-0000-000000000006', 'b3000000-0000-0000-0000-000000000001',
 'Thank you so much, Michelle! We are happy to hear you feel you can trust us with your healthcare. Our team is dedicated to providing compassionate, thorough care. We look forward to seeing you at your next visit.',
 'Thank you, Michelle! Building trust with our patients is everything to us. We''re so glad you''ve found a clinic where you feel comfortable. See you at your next visit!',
 'posted', 0.91, NOW() - INTERVAL '1 day'),

('cc000000-0000-0000-0000-000000000007', 'b3000000-0000-0000-0000-000000000004',
 'Thank you, Carlos! We are proud of our facilities and our dedicated medical team. Your recommendation means a lot to us and to the entire Milton community.',
 'Thank you, Carlos! We take great pride in keeping our clinic clean and up-to-date. Hearing that from a patient means so much to our whole team. Thank you for recommending us!',
 'posted', 0.89, NOW() - INTERVAL '15 days');


-- ─── Review Insights (last 30 days per business) ─────────────────────────────

INSERT INTO review_insights (business_id, period_start, period_end, avg_rating, review_count, response_rate, common_topics, sentiment_score, summary) VALUES

('f02560b2-1ca4-416e-a866-04b9eb9cf69b',
 CURRENT_DATE - INTERVAL '30 days', CURRENT_DATE,
 4.2, 8, 37.5,
 ARRAY['food quality', 'wait times', 'family friendly', 'ambiance', 'pricing'],
 0.72,
 'Your restaurant has a strong 4.2 average over the past 30 days. Customers love your food quality and family-friendly atmosphere. Wait times are the most common complaint — consider staffing improvements during peak hours. 3 of your 5-star reviews mention the tiramisu specifically.'),

('e56bcb43-e709-49bf-a058-0eb605c6fe57',
 CURRENT_DATE - INTERVAL '30 days', CURRENT_DATE,
 3.7, 5, 40.0,
 ARRAY['communication', 'professionalism', 'response time', 'service quality'],
 0.45,
 'Your average rating is 3.7 over the past 30 days. Communication and response time are recurring concerns — 2 reviews specifically mention delayed follow-ups. Your 5-star reviews highlight professionalism and quality of work. Prioritizing faster communication could significantly improve your rating.'),

('7f0d69ee-a946-4821-b16c-843c34ff06f5',
 CURRENT_DATE - INTERVAL '30 days', CURRENT_DATE,
 4.5, 6, 33.3,
 ARRAY['compassionate care', 'wait times', 'appointment availability', 'cleanliness', 'thoroughness'],
 0.81,
 'Excellent performance with a 4.5 average over the past 30 days. Patients consistently praise the compassionate and thorough care. Appointment availability and phone system issues appear in 2 reviews — streamlining your booking process could push you to near-perfect ratings.');
