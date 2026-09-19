import type { ScamAnalysis } from '@/src/types/analysis';

export const loadingSteps = [
  'Checking third-party reputation',
  'Analyzing on-site reviews',
  'Grouping evidence',
];

export const mockAnalysis: ScamAnalysis = {
  store: {
    name: 'Nova Goods',
    domain: 'novagoods.example',
  },
  product: {
    name: 'Minimalist Travel Backpack',
    price: '$49.99',
  },
  overall: {
    riskScore: 61,
    maxScore: 100,
    label: 'Elevated observed risk',
    status: 'medium',
    confidence: 'medium',
    evidenceCount: 12,
    summary: 'Multiple external complaints and suspicious review patterns were detected.',
  },
  categories: [
    {
      id: 'third-party-reputation',
      label: 'Third-Party Reputation',
      riskScore: 72,
      maxScore: 100,
      scoreLabel: 'High concern',
      status: 'high',
      description: 'Independent discussions and reports about the seller.',
      weight: { value: 60, maxValue: 100 },
      evidenceCount: 8,
      sources: [
        {
          id: 'reddit',
          label: 'Reddit',
          riskScore: 72,
          maxScore: 100,
          scoreLabel: 'Several negative reports',
          status: 'high',
          evidenceCount: 8,
          metadata: {
            discussionsFound: 8,
            providerType: 'community-discussion',
          },
        },
      ],
    },
    {
      id: 'onsite-review-quality',
      label: 'On-Site Review Quality',
      riskScore: 46,
      maxScore: 100,
      scoreLabel: 'Some suspicious patterns',
      status: 'medium',
      description: 'Analysis of reviews appearing directly on the store.',
      weight: { value: 40, maxValue: 100 },
      evidenceCount: 4,
      sources: [
        {
          id: 'gptzero',
          label: 'GPTZero',
          riskScore: 46,
          maxScore: 100,
          scoreLabel: 'Some AI-like review patterns',
          status: 'medium',
          evidenceCount: 4,
          metadata: {
            reviewsAnalyzed: 23,
            providerType: 'review-authenticity',
          },
        },
      ],
    },
  ],
  findings: [
    {
      id: 'reddit-nondelivery',
      categoryId: 'third-party-reputation',
      sourceId: 'reddit',
      title: 'Multiple non-delivery reports',
      description: 'Several independent discussions mention orders that never arrived.',
      severity: 'danger',
      evidenceCount: 5,
      evidence: [
        {
          id: 'reddit-thread-1',
          label: 'Reddit discussion',
          source: 'Reddit',
          url: 'https://example.com/reddit-thread-1',
          excerpt: 'Ordered two weeks ago and tracking never updated after the confirmation email.',
          date: '2026-08-29',
          metadata: {
            discussionCount: 14,
          },
        },
        {
          id: 'reddit-thread-2',
          label: 'Follow-up complaint thread',
          source: 'Reddit',
          url: 'https://example.com/reddit-thread-2',
          excerpt: 'Multiple buyers in the thread reported receiving no shipping confirmation.',
          date: '2026-09-03',
        },
      ],
    },
    {
      id: 'reddit-refunds',
      categoryId: 'third-party-reputation',
      sourceId: 'reddit',
      title: 'Refund complaints after delayed shipping',
      description: 'A smaller cluster of posts describe refund requests going unanswered.',
      severity: 'warning',
      evidenceCount: 3,
      evidence: [
        {
          id: 'reddit-thread-3',
          label: 'Refund discussion',
          source: 'Reddit',
          url: 'https://example.com/reddit-thread-3',
          excerpt: 'Support replied once, then stopped responding after I asked for a refund.',
          date: '2026-09-10',
        },
      ],
    },
    {
      id: 'review-ai-pattern',
      categoryId: 'onsite-review-quality',
      sourceId: 'gptzero',
      title: 'Potential AI-generated review patterns',
      description: 'A portion of analyzed reviews showed strong AI-like characteristics.',
      severity: 'warning',
      evidenceCount: 4,
      evidence: [
        {
          id: 'gptzero-review-sample-1',
          label: 'Review language sample',
          source: 'GPTZero',
          excerpt:
            'Several five-star reviews use repeated phrasing around durability, shipping speed, and value.',
          metadata: {
            reviewsFlagged: 9,
            reviewsAnalyzed: 23,
          },
        },
      ],
    },
    {
      id: 'review-inconclusive',
      categoryId: 'onsite-review-quality',
      sourceId: 'gptzero',
      title: 'Remaining reviews inconclusive',
      description: 'Most reviews did not provide enough signal to classify confidently.',
      severity: 'info',
      evidenceCount: 0,
    },
  ],
};

export const insufficientDataAnalysis: ScamAnalysis = {
  store: {
    name: 'Cedar Market',
    domain: 'cedarmarket.example',
  },
  product: {
    name: 'Compact Desk Lamp',
    price: '$34.00',
  },
  overall: {
    riskScore: 0,
    maxScore: 0,
    label: 'Not enough evidence',
    status: 'unknown',
    confidence: 'low',
    evidenceCount: 1,
    summary: 'Not enough independent evidence was found to provide a meaningful estimate.',
  },
  categories: [
    {
      id: 'third-party-reputation',
      label: 'Third-Party Reputation',
      riskScore: 0,
      maxScore: 0,
      scoreLabel: 'Insufficient external discussion',
      status: 'unknown',
      description: 'Independent discussions and reports about the seller.',
      weight: { value: 60, maxValue: 100 },
      evidenceCount: 1,
      sources: [
        {
          id: 'reddit',
          label: 'Reddit',
          scoreLabel: 'Limited matches',
          status: 'unknown',
          evidenceCount: 1,
        },
      ],
    },
    {
      id: 'onsite-review-quality',
      label: 'On-Site Review Quality',
      riskScore: 0,
      maxScore: 0,
      scoreLabel: 'Not enough reviews',
      status: 'unknown',
      description: 'Analysis of reviews appearing directly on the store.',
      weight: { value: 40, maxValue: 100 },
      evidenceCount: 0,
      sources: [
        {
          id: 'gptzero',
          label: 'GPTZero',
          scoreLabel: 'Too few reviews to analyze',
          status: 'unknown',
          evidenceCount: 0,
        },
      ],
    },
  ],
  findings: [
    {
      id: 'limited-discussion',
      categoryId: 'third-party-reputation',
      sourceId: 'reddit',
      title: 'Limited third-party discussion found',
      description: 'Only one low-detail mention was found, so the estimate remains unknown.',
      severity: 'info',
      evidenceCount: 1,
      evidence: [
        {
          id: 'limited-mention-1',
          label: 'Low-detail mention',
          source: 'Reddit',
          excerpt: 'A short mention referenced the store, but did not include a clear purchase outcome.',
          date: '2026-09-12',
        },
      ],
    },
  ],
};
